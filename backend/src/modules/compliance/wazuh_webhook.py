"""
Wazuh → Puppet closed-loop remediation (the platform-side "active response").

This module receives security/compliance alerts forwarded by the Wazuh manager's
integrator daemon and drives the closed remediation loop:

    ① Wazuh detects a violation on an enrolled agent
    ② Manager's integrator POSTs the alert JSON to  POST /api/webhooks/wazuh
    ③ ReceiveWazuhAlertUseCase authenticates, parses and resolves the node
    ④ A ComplianceViolation is recorded + broadcast (compliance.violation_detected)
    ⑤ TriggerRemediationUseCase runs `puppet agent -t` over SSH on the node,
       linking the RemediationEvent back to the originating wazuh_alert_id
    ⑥ When enabled, CollectNodeComplianceUseCase re-scans the node so the
       dashboard reflects the post-enforcement state
    ⑦ Every transition is published on the in-process event bus and streamed to
       the node's WebSocket channel (node-<id>) for live UI updates

Steps ⑤–⑦ run in a background task so the webhook responds to Wazuh immediately
(HTTP 202) instead of holding the integrator open for the length of a Puppet run.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from core.domain.interfaces import IComplianceRepository, INodeRepository
from core.errors import NotFoundError
from core.events import Events

logger = logging.getLogger(__name__)


class WazuhAlert:
    """A thin, defensive view over a raw Wazuh alert document.

    Wazuh alerts vary in shape between rule sets and decoders; every field is
    treated as optional and coerced safely so a malformed payload degrades to a
    clear "could not act" response rather than a 500.
    """

    def __init__(self, raw: dict) -> None:
        self.raw = raw if isinstance(raw, dict) else {}
        rule = self.raw.get("rule") or {}
        agent = self.raw.get("agent") or {}

        # Alert identity — Wazuh uses "id" at the top level; some integrations
        # nest it differently, so fall back through the common locations.
        self.alert_id: str | None = (
            _str(self.raw.get("id"))
            or _str((self.raw.get("data") or {}).get("id"))
            or _str(rule.get("id"))
        )
        self.rule_id: str | None = _str(rule.get("id"))
        self.rule_level: int = _int(rule.get("level"), default=0)
        self.rule_description: str = _str(rule.get("description")) or "Wazuh alert"
        self.rule_groups: list[str] = [g for g in (rule.get("groups") or []) if isinstance(g, str)]

        self.agent_id: str | None = _str(agent.get("id"))
        self.agent_name: str | None = _str(agent.get("name"))
        self.agent_ip: str | None = _str(agent.get("ip"))

        self.full_log: str = _str(self.raw.get("full_log")) or ""
        self.timestamp: str = _str(self.raw.get("timestamp")) or datetime.utcnow().isoformat()

    def summary(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "rule_level": self.rule_level,
            "rule_description": self.rule_description,
            "rule_groups": self.rule_groups,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_ip": self.agent_ip,
            "timestamp": self.timestamp,
        }


def _str(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


class ReceiveWazuhAlertUseCase:
    """Orchestrates the Wazuh → Puppet → re-scan active-response loop."""

    def __init__(
        self,
        node_repo: INodeRepository,
        compliance_repo: IComplianceRepository,
        remediate_uc,
        collect_uc=None,
        event_bus=None,
        ws_manager=None,
        min_level: int = 7,
        rescan: bool = True,
    ) -> None:
        self._nodes = node_repo
        self._repo = compliance_repo
        self._remediate = remediate_uc
        self._collect = collect_uc
        self._bus = event_bus
        self._ws = ws_manager
        self._min_level = min_level
        self._rescan = rescan
        # One in-flight remediation per node — prevents a burst of alerts for the
        # same host from launching concurrent Puppet runs over SSH.
        self._locks: dict[str, asyncio.Lock] = {}
        self._inflight: set[str] = set()

    # ── Public entry point ────────────────────────────────────────────────────

    async def execute(self, raw: dict) -> dict:
        """
        Validate + resolve synchronously, then fire the remediation loop in the
        background. Returns a small acknowledgement describing what was decided
        so the webhook can answer Wazuh in milliseconds.
        """
        alert = WazuhAlert(raw)

        # 1) Severity gate — ignore noise below the configured threshold.
        if alert.rule_level < self._min_level:
            logger.info(
                "Wazuh alert %s ignored: level %s < min %s",
                alert.alert_id, alert.rule_level, self._min_level,
            )
            return {
                "status": "ignored",
                "reason": f"rule level {alert.rule_level} below minimum {self._min_level}",
                "alert": alert.summary(),
            }

        # 2) Resolve the alert's agent to a managed node.
        node = await self._resolve_node(alert)
        if node is None:
            logger.warning(
                "Wazuh alert %s for agent name=%s ip=%s matched no managed node",
                alert.alert_id, alert.agent_name, alert.agent_ip,
            )
            return {
                "status": "unmatched",
                "reason": "no managed node matches the alert's agent (name/ip)",
                "alert": alert.summary(),
            }

        # 3) Record + broadcast the violation immediately (the loop has started).
        self._publish(Events.COMPLIANCE_VIOLATION_DETECTED, {
            "node_id": node.id,
            "hostname": node.hostname,
            "wazuh_alert_id": alert.alert_id,
            "rule_id": alert.rule_id,
            "rule_level": alert.rule_level,
            "rule_description": alert.rule_description,
        })
        await self._broadcast(node.id, "violation_detected", {
            "wazuh_alert_id": alert.alert_id,
            "rule_id": alert.rule_id,
            "rule_level": alert.rule_level,
            "rule_description": alert.rule_description,
            "message": f"Wazuh violation: {alert.rule_description}",
        })

        # 4) Coalesce: if this node already has a remediation in flight, attach
        #    this alert to the audit trail but don't launch a second Puppet run.
        if node.id in self._inflight:
            return {
                "status": "queued",
                "reason": "a remediation is already in progress for this node",
                "node_id": node.id,
                "hostname": node.hostname,
                "alert": alert.summary(),
            }

        if not node.puppet_enrolled:
            # Still record the attempt (skipped) so the node history is honest.
            result = await self._remediate.execute(
                node.id, description=f"Wazuh alert {alert.alert_id}: {alert.rule_description}",
                wazuh_alert_id=alert.alert_id,
            )
            await self._broadcast(node.id, "remediation_skipped", result)
            return {
                "status": "skipped",
                "reason": "node has no Puppet agent enrolled",
                "node_id": node.id,
                "hostname": node.hostname,
                "alert": alert.summary(),
            }

        # 5) Launch the enforcement + re-scan loop in the background.
        self._inflight.add(node.id)
        asyncio.create_task(self._run_loop(node.id, node.hostname, alert))

        return {
            "status": "accepted",
            "node_id": node.id,
            "hostname": node.hostname,
            "action": "puppet enforcement scheduled",
            "rescan": self._rescan and self._collect is not None,
            "alert": alert.summary(),
        }

    # ── Background loop ───────────────────────────────────────────────────────

    async def _run_loop(self, node_id: str, hostname: str, alert: WazuhAlert) -> None:
        lock = self._locks.setdefault(node_id, asyncio.Lock())
        async with lock:
            try:
                self._publish(Events.REMEDIATION_TRIGGERED, {
                    "node_id": node_id,
                    "wazuh_alert_id": alert.alert_id,
                    "rule_description": alert.rule_description,
                })
                await self._broadcast(node_id, "remediation_triggered", {
                    "wazuh_alert_id": alert.alert_id,
                    "message": "Puppet enforcement run started (active response).",
                })

                # ── Puppet enforcement ────────────────────────────────────────
                result = await self._remediate.execute(
                    node_id,
                    description=f"Wazuh alert {alert.alert_id}: {alert.rule_description}",
                    wazuh_alert_id=alert.alert_id,
                )
                self._publish(Events.REMEDIATION_COMPLETED, {
                    "node_id": node_id,
                    "wazuh_alert_id": alert.alert_id,
                    "outcome": result.get("outcome"),
                    "resources_fixed": result.get("resources_fixed", 0),
                })
                await self._broadcast(node_id, "remediation_completed", result)

                # ── Closing the loop: re-scan so the UI shows the new posture ──
                if self._rescan and self._collect is not None:
                    await self._broadcast(node_id, "rescan_started", {
                        "message": "Re-scanning node compliance after remediation.",
                    })
                    try:
                        scan = await self._collect.execute(node_id)
                        await self._broadcast(node_id, "rescan_completed", {
                            "message": "Post-remediation compliance scan complete.",
                            "score": scan.get("score") if isinstance(scan, dict) else None,
                        })
                    except Exception as exc:  # re-scan failure must not mask the fix
                        logger.error("Post-remediation re-scan failed for %s: %s", node_id, exc)
                        await self._broadcast(node_id, "rescan_failed", {"error": str(exc)})
            except Exception as exc:
                logger.error("Wazuh remediation loop failed for %s: %s", node_id, exc)
                await self._broadcast(node_id, "remediation_failed", {
                    "wazuh_alert_id": alert.alert_id,
                    "error": str(exc),
                })
            finally:
                self._inflight.discard(node_id)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _resolve_node(self, alert: WazuhAlert):
        """Match a Wazuh agent to a managed node by hostname, then by IP."""
        if alert.agent_name:
            try:
                node = await self._nodes.find_by_hostname(alert.agent_name)
            except NotFoundError:
                node = None
            if node:
                return node
        if alert.agent_ip:
            try:
                for node in await self._nodes.find_all({}):
                    if node.ip == alert.agent_ip:
                        return node
            except Exception as exc:
                logger.error("Node IP resolution failed: %s", exc)
        return None

    def _publish(self, event_name: str, payload: dict) -> None:
        if self._bus is not None:
            try:
                self._bus.publish(event_name, payload)
            except Exception as exc:
                logger.error("Event publish failed [%s]: %s", event_name, exc)

    async def _broadcast(self, node_id: str, phase: str, payload: dict) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.broadcast_node(node_id, {
                "channel": "remediation",
                "phase": phase,
                "node_id": node_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": payload,
            })
        except Exception as exc:
            logger.error("WebSocket broadcast failed [%s/%s]: %s", node_id, phase, exc)
