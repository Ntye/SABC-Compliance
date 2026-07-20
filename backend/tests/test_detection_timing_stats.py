"""Dashboard timing KPIs: min/max/avg detection and enforcement time per OS family.

Detection time is the agent-observed timestamp -> platform ingest (created_at)
gap; enforcement time is triggered_at -> completed_at on finished remediation
events. Baselines, unfinished remediations and negative gaps (clock skew) must
be excluded rather than skewing the figures.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.domain.entities import ConfigChangeEvent, Node, RemediationEvent
from modules.detection.usecases import GetDetectionTimingStatsUseCase

T0 = datetime(2026, 7, 20, 12, 0, 0)


def _event(node_id, seen_offset_s, ingest_offset_s, event_type="modified"):
    return ConfigChangeEvent(
        id=f"e-{node_id}-{seen_offset_s}-{ingest_offset_s}",
        node_id=node_id,
        path="/etc/ssh/sshd_config",
        event_type=event_type,
        timestamp=T0 + timedelta(seconds=seen_offset_s),
        created_at=T0 + timedelta(seconds=ingest_offset_s),
    )


def _remediation(node_id, duration_s):
    return RemediationEvent(
        id=f"r-{node_id}-{duration_s}",
        node_id=node_id,
        puppet_job_id="job",
        triggered_at=T0,
        completed_at=None if duration_s is None else T0 + timedelta(seconds=duration_s),
        outcome="pending" if duration_s is None else "success",
    )


class FakeNodeRepo:
    def __init__(self, nodes):
        self.nodes = nodes

    async def find_all(self, filters):
        return list(self.nodes)


class FakeDetectionRepo:
    def __init__(self, events):
        self.events = events

    async def find_events(self, node_id=None, limit=100, include_heartbeats=False):
        return list(self.events)


class FakeComplianceRepo:
    def __init__(self, remediations):
        self.remediations = remediations

    async def find_all_remediations(self, limit):
        return list(self.remediations)


def _uc(nodes, events, remediations):
    return GetDetectionTimingStatsUseCase(
        FakeDetectionRepo(events), FakeNodeRepo(nodes), FakeComplianceRepo(remediations),
    )


@pytest.mark.asyncio
async def test_stats_bucketed_by_os_family():
    nodes = [
        Node(id="deb", hostname="deb1", ip="10.0.0.1", os_family="Debian"),
        Node(id="rh", hostname="rh1", ip="10.0.0.2", os_family="RedHat"),
    ]
    events = [
        _event("deb", 0, 2),    # 2s
        _event("deb", 10, 14),  # 4s
        _event("rh", 0, 1),     # 1s
    ]
    remediations = [_remediation("deb", 30), _remediation("rh", 90)]

    out = await _uc(nodes, events, remediations).execute()

    by_fam = {f["os_family"]: f for f in out["families"]}
    assert set(by_fam) == {"Debian", "RedHat"}
    deb = by_fam["Debian"]
    assert deb["detection"] == {"count": 2, "min_s": 2.0, "max_s": 4.0, "avg_s": 3.0}
    assert deb["enforcement"]["count"] == 1 and deb["enforcement"]["avg_s"] == 30.0
    assert by_fam["RedHat"]["detection"]["max_s"] == 1.0
    assert out["overall"]["detection"]["count"] == 3
    assert out["overall"]["enforcement"]["count"] == 2


@pytest.mark.asyncio
async def test_baselines_pending_and_skewed_samples_are_excluded():
    nodes = [Node(id="n1", hostname="h1", ip="10.0.0.1", os_family="Debian")]
    events = [
        _event("n1", 0, 5),                          # counted: 5s
        _event("n1", 0, 1, event_type="baseline"),   # baseline -> excluded
        _event("n1", 100, 40),                       # negative gap (skew) -> excluded
    ]
    remediations = [_remediation("n1", 12), _remediation("n1", None)]  # pending excluded

    out = await _uc(nodes, events, remediations).execute()

    fam = out["families"][0]
    assert fam["detection"] == {"count": 1, "min_s": 5.0, "max_s": 5.0, "avg_s": 5.0}
    assert fam["enforcement"]["count"] == 1 and fam["enforcement"]["min_s"] == 12.0


@pytest.mark.asyncio
async def test_unknown_node_falls_into_unknown_bucket_and_empty_is_shaped():
    out = await _uc([], [_event("ghost", 0, 3)], []).execute()
    assert out["families"][0]["os_family"] == "Unknown"
    assert out["families"][0]["enforcement"] == {
        "count": 0, "min_s": None, "max_s": None, "avg_s": None,
    }

    empty = await _uc([], [], []).execute()
    assert empty["families"] == []
    assert empty["overall"]["detection"]["count"] == 0
