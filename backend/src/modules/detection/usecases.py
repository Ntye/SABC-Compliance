"""
Detection gateway — receives config-change events from the node-side
detection agents, records them as evidence, and re-assesses compliance.

    ① agent spots a change on a watched path (inotify) and snapshots it
    ② agent POSTs the event to POST /api/webhooks/detection
    ③ ReceiveDetectionEventUseCase resolves the node, stores the event as
       EVIDENCE (config_change_events + content-addressed config_blobs)
    ④ the feedback-storm guard decides, in order:
         a. active remediation window (a RemediationEvent with outcome=pending
            exists for the node)      → store suppressed, link, do nothing
         b. puppet_running flag set   → store suppressed (scheduled converge)
         c. otherwise                 → store live, publish
            compliance.violation_detected, and ALWAYS launch a compliance
            SCAN so the dashboard reflects the node's true posture
    ⑤ remediation is decoupled from detection: a genuine change re-scans, but
       Puppet enforcement runs ONLY when the closed loop is explicitly enabled
       — globally (platform config ``detection_closed_loop_enabled``) or for a
       Puppet node group the node belongs to (``active_response_enabled``).
       With the loop off the platform observes and reports; it never
       auto-enforces behind the operator's back.
    ⑥ every stored event is broadcast over WebSocket so the dashboard
       updates live (node-<id> channel + the global detection-events feed)

The agent NEVER suppresses locally — every event reaches this gateway and the
decision (and its reason) is recorded on the stored row, so the evidence trail
stays complete either way.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from core.domain.entities import ConfigChangeEvent, Node
from core.domain.interfaces import (
    IComplianceRepository, IDetectionRepository, INodeRepository,
)
from core.errors import NotFoundError, ValidationError
from core.events import Events

logger = logging.getLogger(__name__)

# Event types that are evidence-only by nature: they are stored but can never
# trigger a scan or remediation, regardless of the suppression rules below.
_PASSIVE_EVENT_TYPES = {"baseline"}
_VALID_EVENT_TYPES = {"created", "modified", "deleted", "moved", "baseline", "heartbeat"}

# Global kill-switch / enable for closed-loop enforcement. Stored in
# platform_config as the string "true"/"false"; absent (or anything else)
# means disabled — detection observes and scans but never auto-remediates.
DETECTION_CLOSED_LOOP_CONFIG_KEY = "detection_closed_loop_enabled"


def _as_bool(raw: Any) -> bool:
    return isinstance(raw, str) and raw.strip().lower() in {"true", "1", "yes", "on"}


def _parse_timestamp(raw: Any) -> datetime:
    if isinstance(raw, str) and raw.strip():
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return datetime.utcnow()


class ReceiveDetectionEventUseCase:
    """Validate, store, decide (suppression), and — for genuine drift — always
    launch a compliance scan, plus a Puppet remediation run when the closed
    loop is enabled. Both run in the background so the webhook answers the agent
    in milliseconds instead of holding it open for the length of a scan/run."""

    def __init__(
        self,
        node_repo: INodeRepository,
        detection_repo: IDetectionRepository,
        compliance_repo: IComplianceRepository,
        remediate_uc: Any,               # TriggerRemediationUseCase
        collect_uc: Any = None,          # CollectNodeComplianceUseCase
        config_repo: Any = None,         # IPlatformConfigRepository
        node_group_repo: Any = None,     # INodeGroupRepository
        event_bus: Any = None,
        ws_manager: Any = None,
    ) -> None:
        self._nodes = node_repo
        self._repo = detection_repo
        self._compliance = compliance_repo
        self._remediate = remediate_uc
        self._collect = collect_uc
        self._config = config_repo
        self._node_groups = node_group_repo
        self._bus = event_bus
        self._ws = ws_manager
        # Closes the race between two events arriving before the first one's
        # RemediationEvent (outcome=pending) is visible in the DB.
        self._inflight: set[str] = set()

    # ── Public entry point ────────────────────────────────────────────────────

    async def execute(self, raw: dict) -> dict:
        node, event, content = await self._validate(raw)

        # Heartbeats: liveness only — replace the previous one, no evidence row.
        if event.event_type == "heartbeat":
            event.suppressed = True
            event.suppress_reason = "heartbeat"
            await self._repo.save_heartbeat(event)
            await self._broadcast(node, event, phase="heartbeat")
            return {"status": "heartbeat", "node_id": node.id, "event_id": event.id}

        # Store the content blob first (content-addressed, deduplicated) so the
        # evidence exists even if anything later in the pipeline fails.
        blob_stored = False
        if content is not None and event.new_hash:
            blob_stored = await self._repo.save_blob(event.new_hash, content)

        # ── Suppression decision (feedback-storm guard) ───────────────────────
        decision = await self._decide(node, event)
        event.suppressed = decision["suppressed"]
        event.suppress_reason = decision.get("reason")
        event.remediation_event_id = decision.get("remediation_event_id")

        await self._repo.save_event(event)
        await self._broadcast(node, event, phase="suppressed" if event.suppressed else "detected")

        result: dict[str, Any] = {
            "status": "suppressed" if event.suppressed else "accepted",
            "node_id": node.id,
            "hostname": node.hostname,
            "event_id": event.id,
            "suppress_reason": event.suppress_reason,
            "remediation_event_id": event.remediation_event_id,
            "blob_stored": blob_stored,
        }

        if not event.suppressed:
            self._publish(Events.COMPLIANCE_VIOLATION_DETECTED, {
                "node_id": node.id,
                "hostname": node.hostname,
                "detection_event_id": event.id,
                "path": event.path,
                "event_type": event.event_type,
                "prev_hash": event.prev_hash,
                "new_hash": event.new_hash,
            })

            # Every genuine change re-assesses compliance: launch a scan so the
            # dashboard reflects the node's true posture after the drift. This
            # happens regardless of whether remediation is enabled.
            actions: list[str] = []
            if self._collect is not None:
                asyncio.create_task(self._run_scan(node, event))
                actions.append("compliance scan scheduled")

            # Remediation is decoupled: only enforce when the closed loop is
            # explicitly enabled (globally or for one of the node's groups).
            closed_loop = await self._closed_loop_enabled(node)
            result["closed_loop"] = closed_loop
            if closed_loop:
                # inflight guard closes the race with the pending-RemediationEvent
                # row so the Puppet run's own writes don't re-trigger.
                self._inflight.add(node.id)
                asyncio.create_task(self._run_remediation(node, event))
                actions.append("puppet remediation scheduled")

            result["action"] = " + ".join(actions) if actions else "recorded"

        return result

    # ── Validation / resolution ───────────────────────────────────────────────

    async def _validate(self, raw: dict) -> tuple[Node, ConfigChangeEvent, Optional[bytes]]:
        if not isinstance(raw, dict):
            raise ValidationError("Event payload must be a JSON object")

        hostname = str(raw.get("node_hostname") or "").strip()
        if not hostname:
            raise ValidationError("node_hostname is required")

        event_type = str(raw.get("event_type") or "").strip().lower()
        if event_type not in _VALID_EVENT_TYPES:
            raise ValidationError(
                f"event_type must be one of {sorted(_VALID_EVENT_TYPES)}"
            )

        path = str(raw.get("path") or "").strip()
        if not path and event_type != "heartbeat":
            raise ValidationError("path is required for non-heartbeat events")

        node = await self._nodes.find_by_hostname(hostname)
        if node is None:
            # Unknown node → the route maps this to HTTP 404 and logs it.
            raise NotFoundError(f"No registered node matches hostname '{hostname}'")

        content: Optional[bytes] = None
        content_b64 = raw.get("content_b64")
        if isinstance(content_b64, str) and content_b64:
            try:
                content = base64.b64decode(content_b64, validate=True)
            except (binascii.Error, ValueError):
                raise ValidationError("content_b64 is not valid base64")

        new_hash = raw.get("new_hash") or None
        if content is not None:
            digest = hashlib.sha256(content).hexdigest()
            if new_hash and new_hash != digest:
                # Trust the content we actually received over the agent's claim.
                logger.warning(
                    "detection event hash mismatch for %s:%s — using computed hash",
                    hostname, path,
                )
            new_hash = digest

        file_meta = raw.get("file_meta") if isinstance(raw.get("file_meta"), dict) else None
        actor = raw.get("actor") if isinstance(raw.get("actor"), dict) else None

        event = ConfigChangeEvent(
            id=str(uuid.uuid4()),
            node_id=node.id,
            path=path,
            event_type=event_type,
            timestamp=_parse_timestamp(raw.get("timestamp")),
            prev_hash=raw.get("prev_hash") or None,
            new_hash=new_hash,
            file_meta=file_meta,
            puppet_running=bool(raw.get("puppet_running")),
            actor=actor,
            created_at=datetime.utcnow(),
        )
        return node, event, content

    # ── Suppression decision ──────────────────────────────────────────────────

    async def _decide(self, node: Node, event: ConfigChangeEvent) -> dict:
        """Feedback-storm guard. Order matters and is part of the contract:

        a. active remediation window → the change is (almost certainly) our own
           Puppet run writing files: store as evidence, link it to the run,
           never re-trigger — this breaks the detect→fix→detect loop.
        b. puppet_running flag → a scheduled converge is writing: same story,
           minus the link (no platform-driven run to point at).
        c. otherwise → genuine drift: store live and let the caller trigger.

        Baseline snapshots are always stored suppressed — they describe the
        starting state, not a change.
        """
        if event.event_type in _PASSIVE_EVENT_TYPES:
            return {"suppressed": True, "reason": "baseline"}

        # (a) active remediation window?
        pending = await self._compliance.find_pending_remediation(node.id)
        if pending is None and node.id in self._inflight:
            # In-process race guard: a trigger was just scheduled but its
            # RemediationEvent row may not be committed yet.
            pending = await self._compliance.find_pending_remediation(node.id)
            if pending is None:
                return {"suppressed": True, "reason": "remediation_pending",
                        "remediation_event_id": None}
        if pending is not None:
            return {"suppressed": True, "reason": "remediation_pending",
                    "remediation_event_id": pending.id}

        # (b) scheduled Puppet converge writing files?
        if event.puppet_running:
            return {"suppressed": True, "reason": "puppet_run"}

        # (c) genuine drift.
        return {"suppressed": False, "reason": None}

    # ── Closed-loop gate ──────────────────────────────────────────────────────

    async def _closed_loop_enabled(self, node: Node) -> bool:
        """True when Puppet enforcement may run automatically for this node.

        Two independent levers, either of which turns the loop on:
          1. the global platform switch ``detection_closed_loop_enabled``;
          2. ``active_response_enabled`` on any Puppet node group the node
             belongs to — per-group active response.
        With neither set the platform observes and scans but never enforces.
        """
        # (1) global switch
        if self._config is not None:
            try:
                if _as_bool(await self._config.get(DETECTION_CLOSED_LOOP_CONFIG_KEY)):
                    return True
            except Exception as exc:
                logger.error("closed-loop config read failed for %s: %s", node.id, exc)

        # (2) per-group active response
        if self._node_groups is not None:
            try:
                groups = await self._node_groups.find_all()
            except Exception as exc:
                logger.error("closed-loop group lookup failed for %s: %s", node.id, exc)
                groups = []
            for g in groups:
                if getattr(g, "active_response_enabled", False) and node.id in (getattr(g, "node_ids", None) or []):
                    return True

        return False

    # ── Background scan (always, on genuine drift) ────────────────────────────

    async def _run_scan(self, node: Node, event: ConfigChangeEvent) -> None:
        try:
            self._publish(Events.SCAN_STARTED, {
                "node_id": node.id,
                "detection_event_id": event.id,
                "trigger": "detection",
            })
            result = await self._collect.execute(node.id)
            self._publish(Events.SCAN_COMPLETED, {
                "node_id": node.id,
                "detection_event_id": event.id,
                "collected": result.get("collected"),
            })
            await self._broadcast(node, event, phase="scan_completed", extra=result)
        except Exception as exc:
            logger.error("Detection-triggered scan failed for %s: %s", node.id, exc)
            await self._broadcast(node, event, phase="scan_failed",
                                  extra={"error": str(exc)})

    # ── Background remediation (only when closed loop is enabled) ──────────────

    async def _run_remediation(self, node: Node, event: ConfigChangeEvent) -> None:
        try:
            self._publish(Events.REMEDIATION_TRIGGERED, {
                "node_id": node.id,
                "detection_event_id": event.id,
                "path": event.path,
            })
            result = await self._remediate.execute(
                node.id,
                description=f"Detection event {event.id}: {event.event_type} {event.path}",
                detection_event_id=event.id,
            )
            self._publish(Events.REMEDIATION_COMPLETED, {
                "node_id": node.id,
                "detection_event_id": event.id,
                "outcome": result.get("outcome"),
                "resources_fixed": result.get("resources_fixed", 0),
            })
            await self._broadcast(node, event, phase="remediation_completed", extra=result)
        except Exception as exc:
            logger.error("Detection-triggered remediation failed for %s: %s", node.id, exc)
            await self._broadcast(node, event, phase="remediation_failed",
                                  extra={"error": str(exc)})
        finally:
            self._inflight.discard(node.id)

    # ── Plumbing ──────────────────────────────────────────────────────────────

    def _publish(self, event_name: str, payload: dict) -> None:
        if self._bus is None:
            return
        try:
            self._bus.publish(event_name, payload)
        except Exception as exc:
            logger.error("Event publish failed [%s]: %s", event_name, exc)

    async def _broadcast(self, node: Node, event: ConfigChangeEvent,
                         phase: str, extra: Optional[dict] = None) -> None:
        """Live dashboard feed: the node's channel + the global detection feed."""
        if self._ws is None:
            return
        message = {
            "channel": "detection",
            "phase": phase,
            "node_id": node.id,
            "hostname": node.hostname,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "event_id": event.id,
                "path": event.path,
                "event_type": event.event_type,
                "prev_hash": event.prev_hash,
                "new_hash": event.new_hash,
                "puppet_running": event.puppet_running,
                "suppressed": event.suppressed,
                "suppress_reason": event.suppress_reason,
                "actor": event.actor,
                **(extra or {}),
            },
        }
        try:
            await self._ws.broadcast_node(node.id, message)
            await self._ws.broadcast("detection-events", message)
        except Exception as exc:
            logger.error("Detection WebSocket broadcast failed [%s]: %s", node.id, exc)


class ListDetectionEventsUseCase:
    """Detection Events page: recent events, optionally filtered by node."""

    def __init__(self, detection_repo: IDetectionRepository,
                 node_repo: INodeRepository) -> None:
        self._repo = detection_repo
        self._nodes = node_repo

    async def execute(self, node_id: str | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit or 100), 500))
        events = await self._repo.find_events(node_id=node_id, limit=limit)
        hostnames = {n.id: n.hostname for n in await self._nodes.find_all({})}
        return [
            {
                "id": e.id,
                "node_id": e.node_id,
                "hostname": hostnames.get(e.node_id, e.node_id),
                "path": e.path,
                "event_type": e.event_type,
                "timestamp": e.timestamp.isoformat(),
                "prev_hash": e.prev_hash,
                "new_hash": e.new_hash,
                "file_meta": e.file_meta,
                "puppet_running": e.puppet_running,
                "actor": e.actor,
                "suppressed": e.suppressed,
                "suppress_reason": e.suppress_reason,
                "remediation_event_id": e.remediation_event_id,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]


class GetConfigBlobUseCase:
    """Fetch a content-addressed file snapshot by hash for the diff modal.

    The remediation view is a diff of the previous snapshot against the new one;
    the frontend fetches both blobs by their ``prev_hash`` / ``new_hash``. Text
    is decoded best-effort and capped so a large or binary blob can't wedge the
    UI — ``is_binary`` / ``truncated`` tell the client what it's looking at.
    """

    # Hard cap on the text returned to the browser (bytes). A config file well
    # over this is pathological; the diff stays useful without shipping MBs.
    MAX_TEXT_BYTES = 512 * 1024

    def __init__(self, detection_repo: IDetectionRepository) -> None:
        self._repo = detection_repo

    async def execute(self, sha256: str) -> dict:
        sha = (sha256 or "").strip().lower()
        if not sha:
            raise ValidationError("A blob hash is required")

        blob = await self._repo.find_blob(sha)
        if blob is None:
            raise NotFoundError(f"No stored snapshot for hash '{sha}'")

        content: bytes = blob["content"] or b""
        truncated = len(content) > self.MAX_TEXT_BYTES
        head = content[: self.MAX_TEXT_BYTES]
        try:
            text = head.decode("utf-8")
            is_binary = "\x00" in text
        except UnicodeDecodeError:
            text = ""
            is_binary = True

        return {
            "sha256": blob["sha256"],
            "size": blob["size"],
            "first_seen_at": blob["first_seen_at"],
            "text": "" if is_binary else text,
            "is_binary": is_binary,
            "truncated": truncated,
        }


class GetNodeDetectionStatusUseCase:
    """Node detail page: agent last-seen + per-watched-path status."""

    def __init__(self, detection_repo: IDetectionRepository,
                 node_repo: INodeRepository) -> None:
        self._repo = detection_repo
        self._nodes = node_repo

    async def execute(self, id_or_hostname: str) -> dict:
        node = await self._nodes.find_by_id(id_or_hostname)
        if not node:
            node = await self._nodes.find_by_hostname(id_or_hostname)
        if not node:
            raise NotFoundError(f"Node '{id_or_hostname}' not found")

        status = await self._repo.node_status(node.id)
        status["hostname"] = node.hostname
        status["detection_enrolled"] = node.detection_enrolled
        return status
