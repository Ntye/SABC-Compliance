"""Suppression + scan/remediation decision logic of the detection gateway.

Contract (in priority order):
  a. active remediation window (RemediationEvent outcome=pending for the node)
     -> store suppressed, link remediation_event_id, do NOT scan or trigger
  b. puppet_running flag on the event -> store suppressed, do NOT scan or trigger
  c. otherwise -> store live, publish compliance.violation_detected and ALWAYS
     launch a compliance scan; trigger Puppet remediation ONLY when the closed
     loop is enabled (global config or a node group's active_response).
Baselines are always stored suppressed; heartbeats only refresh liveness.
"""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
from typing import Any, Optional

import pytest

from core.domain.entities import ConfigChangeEvent, Node, RemediationEvent, Tier
from core.errors import NotFoundError, ValidationError
from modules.detection.usecases import (
    GetConfigBlobUseCase, ReceiveDetectionEventUseCase,
)


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

    async def update_violation(self, event_id, violation, detail) -> None:
        for e in self.events:
            if e.id == event_id:
                e.violation, e.violation_detail = violation, detail

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

    async def find_blob(self, sha256: str):
        content = self.blobs.get(sha256)
        if content is None:
            return None
        return {"sha256": sha256, "content": content, "size": len(content),
                "first_seen_at": "2026-01-01T00:00:00"}

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

    async def find_by_node(self, node_id: str) -> list:
        # No prior scan in these suppression tests → the change is left
        # unassessed (violation None), so the closed loop still remediates.
        return []


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


class FakeCollectUC:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, id_or_hostname: str) -> dict:
        self.calls.append(id_or_hostname)
        return {"collected": [{"profile_id": "sabc-baseline"}]}


class FakeConfigRepo:
    def __init__(self, values: Optional[dict[str, str]] = None) -> None:
        self.values = dict(values or {})

    async def get(self, key: str) -> Optional[str]:
        return self.values.get(key)

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value


class FakeNodeGroup:
    def __init__(self, node_ids: list[str], active_response_enabled: bool = False) -> None:
        self.node_ids = node_ids
        self.active_response_enabled = active_response_enabled


class FakeNodeGroupRepo:
    def __init__(self, groups: Optional[list[FakeNodeGroup]] = None) -> None:
        self.groups = list(groups or [])

    async def find_all(self) -> list[FakeNodeGroup]:
        return self.groups


class FakeTierRepo:
    """Serves tiers by id so _closed_loop_enabled can read a node's tier.enforce."""
    def __init__(self, tiers: Optional[dict] = None) -> None:
        self.tiers = dict(tiers or {})

    async def find_by_id(self, tier_id: str):
        return self.tiers.get(tier_id)


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


def make_uc(pending: Optional[RemediationEvent] = None, *,
            collect: Optional["FakeCollectUC"] = None,
            config: Optional["FakeConfigRepo"] = None,
            groups: Optional[list["FakeNodeGroup"]] = None,
            node: Optional[Node] = None,
            tiers: Optional[dict] = None):
    node_repo = FakeNodeRepo([node or NODE])
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
        collect_uc=collect,
        config_repo=config,
        node_group_repo=FakeNodeGroupRepo(groups) if groups is not None else None,
        tier_repo=FakeTierRepo(tiers) if tiers is not None else None,
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


@pytest.mark.asyncio
async def test_suppressed_event_does_not_scan() -> None:
    # A suppressed event is evidence only — it must not launch a scan either.
    pending = RemediationEvent(
        id="rem-99", node_id="node-1", puppet_job_id="ssh-puppet-run",
        triggered_at=datetime.utcnow(), outcome="pending",
    )
    collect = FakeCollectUC()
    uc, _, remediate, _, _ = make_uc(pending=pending, collect=collect)

    result = await run_and_settle(uc, payload())

    assert result["status"] == "suppressed"
    assert collect.calls == []
    assert remediate.calls == []


@pytest.mark.asyncio
async def test_expired_pending_window_does_not_suppress() -> None:
    # A window whose job died without closing it (backend restart, SIGKILL)
    # must not suppress the node's genuine events forever: past the max age
    # rule (a) ignores it and the event is treated as live drift.
    stale = RemediationEvent(
        id="rem-stale", node_id="node-1", puppet_job_id="enforce-referential",
        triggered_at=datetime.utcnow() - timedelta(hours=3), outcome="pending",
    )
    uc, repo, _, bus, _ = make_uc(pending=stale)

    result = await run_and_settle(uc, payload())

    assert result["status"] == "accepted"
    assert repo.events[0].suppressed is False
    assert any(name == "compliance.violation_detected" for name, _ in bus.published)


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


# ── Rule (c): genuine drift always scans, remediates only if closed-loop ──────

@pytest.mark.asyncio
async def test_genuine_drift_scans_but_does_not_remediate_by_default() -> None:
    # Closed loop off (no config, no active-response group) → scan, never enforce.
    collect = FakeCollectUC()
    uc, repo, remediate, bus, ws = make_uc(collect=collect)

    result = await run_and_settle(uc, payload())

    assert result["status"] == "accepted"
    assert result["closed_loop"] is False
    assert result["action"] == "compliance scan scheduled"
    stored = repo.events[0]
    assert stored.suppressed is False and stored.suppress_reason is None

    # scan ran against the node; remediation did NOT
    assert collect.calls == ["node-1"]
    assert remediate.calls == []

    # event bus saw the violation
    names = [name for name, _ in bus.published]
    assert "compliance.violation_detected" in names
    assert "compliance.scan_started" in names

    # live dashboard broadcast on both channels
    assert any(nid == "node-1" for nid, _ in ws.node_messages)
    assert any(ch == "detection-events" for ch, _ in ws.channel_messages)


@pytest.mark.asyncio
async def test_global_closed_loop_enables_remediation() -> None:
    collect = FakeCollectUC()
    config = FakeConfigRepo({"detection_closed_loop_enabled": "true"})
    uc, repo, remediate, bus, _ = make_uc(collect=collect, config=config)

    result = await run_and_settle(uc, payload())

    assert result["closed_loop"] is True
    assert result["action"] == "compliance scan scheduled + remediation gated on violation"
    assert collect.calls == ["node-1"]
    assert len(remediate.calls) == 1
    assert remediate.calls[0]["detection_event_id"] == repo.events[0].id


@pytest.mark.asyncio
async def test_group_active_response_enables_remediation() -> None:
    # Global switch off, but the node is in a group with active_response on.
    collect = FakeCollectUC()
    config = FakeConfigRepo({"detection_closed_loop_enabled": "false"})
    groups = [FakeNodeGroup(node_ids=["node-1"], active_response_enabled=True)]
    uc, repo, remediate, _, _ = make_uc(collect=collect, config=config, groups=groups)

    result = await run_and_settle(uc, payload())

    assert result["closed_loop"] is True
    assert len(remediate.calls) == 1


@pytest.mark.asyncio
async def test_other_groups_active_response_does_not_leak() -> None:
    # Active response is on for a group the node is NOT a member of → loop stays off.
    collect = FakeCollectUC()
    groups = [FakeNodeGroup(node_ids=["someone-else"], active_response_enabled=True)]
    uc, _, remediate, _, _ = make_uc(collect=collect, groups=groups)

    result = await run_and_settle(uc, payload())

    assert result["closed_loop"] is False
    assert remediate.calls == []


# ── Enforcement is driven by the node's tier (Axis 2) ─────────────────────────

@pytest.mark.asyncio
async def test_enforcing_tier_enables_remediation() -> None:
    # Global switch off, no active-response groups, but the node sits on an
    # enforcing tier (Tier 3/4) → the closed loop runs.
    collect = FakeCollectUC()
    node = Node(id="node-1", hostname="web-01", ip="10.0.0.5",
                puppet_enrolled=True, tier_id="tier-3")
    tiers = {"tier-3": Tier(id="tier-3", name="Tier 3", enforce=True, is_system=True)}
    uc, repo, remediate, _, _ = make_uc(
        collect=collect, config=FakeConfigRepo({"detection_closed_loop_enabled": "false"}),
        node=node, tiers=tiers,
    )

    result = await run_and_settle(uc, payload())

    assert result["closed_loop"] is True
    assert len(remediate.calls) == 1


@pytest.mark.asyncio
async def test_validation_only_tier_does_not_remediate() -> None:
    # A node on a validation-only tier (Tier 1/2) is scanned but never enforced.
    collect = FakeCollectUC()
    node = Node(id="node-1", hostname="web-01", ip="10.0.0.5",
                puppet_enrolled=True, tier_id="tier-2")
    tiers = {"tier-2": Tier(id="tier-2", name="Tier 2",
                            includes_level_2=True, enforce=False, is_system=True)}
    uc, _, remediate, _, _ = make_uc(collect=collect, node=node, tiers=tiers)

    result = await run_and_settle(uc, payload())

    assert result["closed_loop"] is False
    assert remediate.calls == []
    assert collect.calls == ["node-1"]   # still scanned


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


# ── Blob fetch (diff modal) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_blob_returns_decoded_text() -> None:
    repo = FakeDetectionRepo()
    content = b"PermitRootLogin no\n"
    import hashlib
    sha = hashlib.sha256(content).hexdigest()
    repo.blobs[sha] = content

    out = await GetConfigBlobUseCase(repo).execute(sha)

    assert out["sha256"] == sha
    assert out["text"] == "PermitRootLogin no\n"
    assert out["is_binary"] is False
    assert out["truncated"] is False
    assert out["size"] == len(content)


@pytest.mark.asyncio
async def test_get_blob_flags_binary_content() -> None:
    repo = FakeDetectionRepo()
    content = b"\x00\x01\x02\xff\xfe"
    import hashlib
    sha = hashlib.sha256(content).hexdigest()
    repo.blobs[sha] = content

    out = await GetConfigBlobUseCase(repo).execute(sha)

    assert out["is_binary"] is True
    assert out["text"] == ""


@pytest.mark.asyncio
async def test_get_blob_missing_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        await GetConfigBlobUseCase(FakeDetectionRepo()).execute("deadbeef")


@pytest.mark.asyncio
async def test_get_blob_empty_hash_rejected() -> None:
    with pytest.raises(ValidationError):
        await GetConfigBlobUseCase(FakeDetectionRepo()).execute("   ")


# ── Rule (c): sanctioned write by the platform's own management account ────────

@pytest.mark.asyncio
async def test_management_actor_write_is_suppressed_not_alert() -> None:
    # Puppet enforcement runs over SSH as the node's management user (ansible),
    # so a change attributed to that account is a sanctioned platform action.
    collect = FakeCollectUC()
    uc, repo, remediate, _, _ = make_uc(collect=collect)

    result = await run_and_settle(
        uc, payload(actor={"auid": 1002, "uid": 0, "username": "ansible",
                           "exe": "/opt/puppetlabs/puppet/bin/puppet", "comm": "puppet"}))

    assert result["status"] == "suppressed"
    assert result["suppress_reason"] == "platform_actor"
    assert repo.events[0].suppressed is True
    # No scan or remediation for our own sanctioned write.
    assert collect.calls == []
    assert remediate.calls == []


@pytest.mark.asyncio
async def test_human_actor_write_is_genuine_drift() -> None:
    # A change by a real user (not the management account) is genuine drift.
    collect = FakeCollectUC()
    uc, repo, _, _, _ = make_uc(collect=collect)

    result = await run_and_settle(
        uc, payload(actor={"auid": 1000, "uid": 1000, "username": "alice",
                           "exe": "/usr/bin/vim", "comm": "vim"}))

    assert result["status"] == "accepted"
    assert repo.events[0].suppressed is False


@pytest.mark.asyncio
async def test_missing_actor_is_not_treated_as_platform() -> None:
    # No attributable actor → cannot claim it was us; stays genuine drift.
    collect = FakeCollectUC()
    uc, repo, _, _, _ = make_uc(collect=collect)

    result = await run_and_settle(uc, payload(actor=None))

    assert result["status"] == "accepted"
    assert repo.events[0].suppressed is False
