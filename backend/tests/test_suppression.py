"""Suppression decision logic of the detection gateway.

Contract (in priority order):
  a. active remediation window (RemediationEvent outcome=pending for the node)
     -> store suppressed, link remediation_event_id, do NOT trigger
  b. puppet_running flag on the event -> store suppressed, do NOT trigger
  c. otherwise -> store live, publish compliance.violation_detected and
     trigger Puppet remediation with detection_event_id=event.id
Baselines are always stored suppressed; heartbeats only refresh liveness.
"""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from typing import Any, Optional

import pytest

from core.domain.entities import ConfigChangeEvent, Node, RemediationEvent
from core.errors import NotFoundError, ValidationError
from modules.detection.usecases import ReceiveDetectionEventUseCase


# ── Test doubles ──────────────────────────────────────────────────────────────

class FakeNodeRepo:
    def __init__(self, nodes: list[Node]) -> None:
        self._nodes = {n.hostname: n for n in nodes}

    async def find_by_hostname(self, hostname: str) -> Optional[Node]:
        return self._nodes.get(hostname)

    async def find_by_id(self, id: str) -> Optional[Node]:
        return next((n for n in self._nodes.values() if n.id == id), None)

    async def find_all(self, filters: dict) -> list[Node]:
        return list(self._nodes.values())


class FakeDetectionRepo:
    def __init__(self) -> None:
        self.events: list[ConfigChangeEvent] = []
        self.heartbeats: list[ConfigChangeEvent] = []
        self.blobs: dict[str, bytes] = {}

    async def save_event(self, event: ConfigChangeEvent) -> None:
        self.events.append(event)

    async def save_heartbeat(self, event: ConfigChangeEvent) -> None:
        self.heartbeats.append(event)

    async def save_blob(self, sha256: str, content: bytes) -> bool:
        if sha256 in self.blobs:
            return False
        self.blobs[sha256] = content
        return True

    async def find_events(self, node_id=None, limit=100, include_heartbeats=False):
        return self.events[-limit:]

    async def find_event(self, id: str):
        return next((e for e in self.events if e.id == id), None)

    async def node_status(self, node_id: str) -> dict:
        return {"node_id": node_id, "agent_last_seen": None,
                "watched_paths": [], "recent_events": 0}


class FakeComplianceRepo:
    def __init__(self, pending: Optional[RemediationEvent] = None) -> None:
        self.pending = pending

    async def find_pending_remediation(self, node_id: str) -> Optional[RemediationEvent]:
        if self.pending and self.pending.node_id == node_id:
            return self.pending
        return None


class FakeRemediateUC:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, node_id: str, description: str | None = None,
                      detection_event_id: str | None = None) -> dict:
        self.calls.append({
            "node_id": node_id,
            "description": description,
            "detection_event_id": detection_event_id,
        })
        return {"outcome": "success", "resources_fixed": 1}


class FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    def publish(self, name: str, payload: dict) -> None:
        self.published.append((name, payload))


class FakeWs:
    def __init__(self) -> None:
        self.node_messages: list[tuple[str, dict]] = []
        self.channel_messages: list[tuple[str, dict]] = []

    async def broadcast_node(self, node_id: str, message: dict) -> None:
        self.node_messages.append((node_id, message))

    async def broadcast(self, channel: str, message: dict) -> None:
        self.channel_messages.append((channel, message))


# ── Fixtures ──────────────────────────────────────────────────────────────────

NODE = Node(id="node-1", hostname="web-01", ip="10.0.0.5", puppet_enrolled=True)


def make_uc(pending: Optional[RemediationEvent] = None):
    node_repo = FakeNodeRepo([NODE])
    detection_repo = FakeDetectionRepo()
    compliance_repo = FakeComplianceRepo(pending)
    remediate = FakeRemediateUC()
    bus = FakeBus()
    ws = FakeWs()
    uc = ReceiveDetectionEventUseCase(
        node_repo=node_repo,
        detection_repo=detection_repo,
        compliance_repo=compliance_repo,
        remediate_uc=remediate,
        event_bus=bus,
        ws_manager=ws,
    )
    return uc, detection_repo, remediate, bus, ws


def payload(**overrides: Any) -> dict:
    base = {
        "node_hostname": "web-01",
        "path": "/etc/ssh/sshd_config",
        "event_type": "modified",
        "timestamp": datetime.utcnow().isoformat(),
        "prev_hash": "aaa",
        "new_hash": "bbb",
        "file_meta": {"mode": "0o600", "uid": 0, "gid": 0, "size": 10, "mtime": 1.0},
        "puppet_running": False,
        "actor": {"auid": 1000, "exe": "/usr/bin/vim", "comm": "vim"},
    }
    base.update(overrides)
    return base


async def run_and_settle(uc, raw: dict) -> dict:
    """Execute and let the background remediation task (if any) finish."""
    result = await uc.execute(raw)
    await asyncio.sleep(0)   # yield so create_task-ed coroutines run
    await asyncio.sleep(0)
    return result


# ── Rule (a): active remediation window ───────────────────────────────────────

@pytest.mark.asyncio
async def test_pending_remediation_suppresses_and_links() -> None:
    pending = RemediationEvent(
        id="rem-42", node_id="node-1", puppet_job_id="ssh-puppet-run",
        triggered_at=datetime.utcnow(), outcome="pending",
    )
    uc, repo, remediate, bus, _ = make_uc(pending=pending)

    result = await run_and_settle(uc, payload())

    assert result["status"] == "suppressed"
    assert result["suppress_reason"] == "remediation_pending"
    assert result["remediation_event_id"] == "rem-42"
    assert len(repo.events) == 1
    stored = repo.events[0]
    assert stored.suppressed is True
    assert stored.remediation_event_id == "rem-42"
    assert remediate.calls == []                      # nothing triggered
    assert all(name != "compliance.violation_detected" for name, _ in bus.published)


# ── Rule (b): puppet_running ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_puppet_running_suppresses_without_link() -> None:
    uc, repo, remediate, bus, _ = make_uc()

    result = await run_and_settle(uc, payload(puppet_running=True))

    assert result["status"] == "suppressed"
    assert result["suppress_reason"] == "puppet_run"
    assert result["remediation_event_id"] is None
    assert repo.events[0].suppressed is True
    assert remediate.calls == []
    assert all(name != "compliance.violation_detected" for name, _ in bus.published)


@pytest.mark.asyncio
async def test_pending_window_wins_over_puppet_flag() -> None:
    # Order matters: rule (a) is checked before rule (b), so the event links
    # to the remediation even when the puppet_running flag is also set.
    pending = RemediationEvent(
        id="rem-7", node_id="node-1", puppet_job_id="ssh-puppet-run",
        triggered_at=datetime.utcnow(), outcome="pending",
    )
    uc, repo, _, _, _ = make_uc(pending=pending)

    result = await run_and_settle(uc, payload(puppet_running=True))

    assert result["suppress_reason"] == "remediation_pending"
    assert result["remediation_event_id"] == "rem-7"


# ── Rule (c): genuine drift triggers the loop ─────────────────────────────────

@pytest.mark.asyncio
async def test_genuine_drift_triggers_remediation_and_publishes() -> None:
    uc, repo, remediate, bus, ws = make_uc()

    result = await run_and_settle(uc, payload())

    assert result["status"] == "accepted"
    assert result["action"] == "puppet remediation scheduled"
    stored = repo.events[0]
    assert stored.suppressed is False and stored.suppress_reason is None

    # remediation triggered with the detection event linked
    assert len(remediate.calls) == 1
    assert remediate.calls[0]["node_id"] == "node-1"
    assert remediate.calls[0]["detection_event_id"] == stored.id

    # event bus saw the violation
    names = [name for name, _ in bus.published]
    assert "compliance.violation_detected" in names

    # live dashboard broadcast on both channels
    assert any(nid == "node-1" for nid, _ in ws.node_messages)
    assert any(ch == "detection-events" for ch, _ in ws.channel_messages)


# ── Passive event types ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_baseline_is_stored_suppressed_and_never_triggers() -> None:
    uc, repo, remediate, _, _ = make_uc()

    result = await run_and_settle(uc, payload(event_type="baseline", prev_hash=None))

    assert result["status"] == "suppressed"
    assert result["suppress_reason"] == "baseline"
    assert repo.events[0].suppressed is True
    assert remediate.calls == []


@pytest.mark.asyncio
async def test_heartbeat_updates_liveness_only() -> None:
    uc, repo, remediate, _, _ = make_uc()

    result = await run_and_settle(uc, payload(
        event_type="heartbeat", path="", prev_hash=None, new_hash=None,
        file_meta=None, actor=None,
    ))

    assert result["status"] == "heartbeat"
    assert repo.events == []                # no evidence row
    assert len(repo.heartbeats) == 1        # liveness row replaced
    assert remediate.calls == []


# ── Blob storage ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_content_blob_stored_and_deduplicated() -> None:
    uc, repo, _, _, _ = make_uc()
    content = b"PermitRootLogin no\n"
    b64 = base64.b64encode(content).decode()

    r1 = await run_and_settle(uc, payload(content_b64=b64))
    r2 = await run_and_settle(uc, payload(content_b64=b64, puppet_running=True))

    assert r1["blob_stored"] is True
    assert r2["blob_stored"] is False       # same content -> deduplicated
    assert len(repo.blobs) == 1
    import hashlib
    assert list(repo.blobs) == [hashlib.sha256(content).hexdigest()]
    # gateway trusts the received content over the agent-claimed hash
    assert repo.events[0].new_hash == hashlib.sha256(content).hexdigest()


# ── Validation / resolution ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_node_raises_not_found() -> None:
    uc, repo, remediate, _, _ = make_uc()
    with pytest.raises(NotFoundError):
        await uc.execute(payload(node_hostname="ghost-host"))
    assert repo.events == [] and remediate.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    {"node_hostname": ""},
    {"event_type": "explosion"},
    {"path": "", "event_type": "modified"},
    {"content_b64": "!!!not-base64!!!"},
])
async def test_invalid_payloads_rejected(bad: dict) -> None:
    uc, repo, _, _, _ = make_uc()
    with pytest.raises(ValidationError):
        await uc.execute(payload(**bad))
    assert repo.events == []
