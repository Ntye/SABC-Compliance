"""Scan execution wiring (Section 6): control filtering + report tagging."""
from __future__ import annotations

import asyncio
import json

import pytest

from core.domain.entities import (
    TIER_1_ID, TIER_2_ID, SABC_BASELINE_PROFILE_ID,
    ComplianceGroup, Node, Profile, ProfileControl, Tier,
)
from modules.compliance.scan_resolver import ScanPlanResolver
from modules.compliance.usecases import (
    CollectNodeComplianceUseCase, ScanComplianceGroupUseCase,
)


# ── Fakes ─────────────────────────────────────────────────────────────────────

def _c(cid, level, applies="debian;redhat"):
    return ProfileControl(id=cid, profile_id="std", section_id="s", section="S",
                          title=cid, kind="control", control_id=cid,
                          cis_level=level, applies_to=applies)


CONTROLS = [_c("c1", 1), _c("c2", 1, "debian"), _c("c3", 2), _c("c4", 2, "redhat")]


class FakeProfileRepo:
    def __init__(self):
        self.p = {"std": Profile(id="std", name="Standard X", version="2.1.0", controls=CONTROLS),
                  SABC_BASELINE_PROFILE_ID: Profile(id=SABC_BASELINE_PROFILE_ID, name="SABC Baseline",
                                                    version="1.0.0", controls=CONTROLS)}
    async def find_by_id(self, i): return self.p.get(i)
    async def find_all(self): return list(self.p.values())


class FakeTierRepo:
    def __init__(self):
        self.t = {TIER_1_ID: Tier(id=TIER_1_ID, name="Tier 1", is_system=True),
                  TIER_2_ID: Tier(id=TIER_2_ID, name="Tier 2", includes_level_2=True, is_system=True)}
    async def find_by_id(self, i): return self.t.get(i)


class FakeGroupRepo:
    def __init__(self, groups): self.groups = groups
    async def find_by_id(self, i): return next((g for g in self.groups if g.id == i), None)
    async def find_for_node(self, nid): return [g for g in self.groups if nid in g.node_ids]


class FakeNodeRepo:
    def __init__(self, nodes): self.nodes = {n.id: n for n in nodes}
    async def find_by_id(self, i): return self.nodes.get(i)
    async def find_by_hostname(self, h): return next((n for n in self.nodes.values() if n.hostname == h), None)
    async def find_all(self, f): return list(self.nodes.values())
    async def update(self, n): self.nodes[n.id] = n


class RecordingComplianceRepo:
    def __init__(self): self.saved = []
    async def save_report(self, r): self.saved.append(r)


def _inspec_json(control_ids):
    return json.dumps({
        "profiles": [{
            "name": "sabc-baseline",
            "controls": [
                {"id": cid, "title": cid, "impact": 0.5,
                 "results": [{"status": "passed"}], "tags": {}}
                for cid in control_ids
            ],
        }],
        "statistics": {"duration": 1.2},
    })


class FakeProc:
    def __init__(self, stdout): self._stdout = stdout.encode()
    async def communicate(self): return self._stdout, b""


def _patch_cinc(monkeypatch, captured):
    """Patch subprocess + engine availability so no real CINC/SSH is needed.
    Echoes back exactly the controls passed via --controls as passed results."""
    async def fake_exec(*args, **kw):
        captured["args"] = list(args)
        # controls requested = tokens after '--controls' up to the next flag
        ids = []
        if "--controls" in args:
            i = args.index("--controls") + 1
            while i < len(args) and not args[i].startswith("-"):
                ids.append(args[i]); i += 1
        return FakeProc(_inspec_json(ids))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)


def build_collect(monkeypatch, captured, nodes, groups):
    prof = FakeProfileRepo()
    resolver = ScanPlanResolver(FakeNodeRepo(nodes), FakeGroupRepo(groups), FakeTierRepo(),
                                prof, inspec_dir_for=lambda p: "/tmp")   # dir must exist
    repo = RecordingComplianceRepo()
    uc = CollectNodeComplianceUseCase(FakeNodeRepo(nodes), repo, ssh=None,
                                      profile_path="/tmp", scan_resolver=resolver)
    uc._scan_engine_available = lambda: True
    uc._scan_bin = "/bin/sh"   # a real file so the binary-existence guard passes
    _patch_cinc(monkeypatch, captured)
    return uc, repo, resolver


def node(nid, family, tier=TIER_1_ID):
    return Node(id=nid, hostname=nid, ip="10.0.0.9", ssh_user="ansible", os_family=family, tier_id=tier)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestControlFiltering:
    async def test_only_tier_family_controls_passed_to_cinc(self, monkeypatch, tmp_path) -> None:
        captured = {}
        n = node("n1", "Debian")  # non-critical debian → c1, c2
        g = ComplianceGroup(id="g", name="G", profile_ids=["std"], node_ids=["n1"])
        uc, repo, _ = build_collect(monkeypatch, captured, [n], [g])
        result = await uc.execute("n1")
        assert "--controls" in captured["args"]
        idx = captured["args"].index("--controls")
        passed = set(captured["args"][idx + 1:idx + 5]) & {"c1", "c2", "c3", "c4"}
        assert passed == {"c1", "c2"}
        assert result["collected"]

    async def test_critical_redhat_passes_l2_redhat_control(self, monkeypatch) -> None:
        captured = {}
        n = node("n1", "RedHat", tier=TIER_2_ID)  # → c1, c3, c4
        g = ComplianceGroup(id="g", name="G", profile_ids=["std"], node_ids=["n1"])
        uc, _, _ = build_collect(monkeypatch, captured, [n], [g])
        await uc.execute("n1")
        args = captured["args"]
        idx = args.index("--controls")
        got = []
        i = idx + 1
        while i < len(args) and not args[i].startswith("-"):
            got.append(args[i]); i += 1
        assert set(got) == {"c1", "c3", "c4"}


class TestReportTagging:
    async def test_report_tagged_with_group_profile_tier_family(self, monkeypatch) -> None:
        captured = {}
        n = node("n1", "Debian")
        g = ComplianceGroup(id="g1", name="Prod", profile_ids=["std"], node_ids=["n1"])
        uc, repo, _ = build_collect(monkeypatch, captured, [n], [g])
        await uc.execute("n1")
        r = repo.saved[0]
        assert r.profile_id == "std" and r.profile_version == "2.1.0"
        assert r.compliance_group_id == "g1"
        assert r.tier_name == "Tier 1"
        assert r.os_family == "debian"


class TestGroupScan:
    async def test_group_scan_iterates_members(self, monkeypatch) -> None:
        captured = {}
        d = node("d", "Debian")
        r = node("r", "RedHat", tier=TIER_2_ID)
        g = ComplianceGroup(id="g", name="Mixed", profile_ids=["std"], node_ids=["d", "r"])
        uc, repo, resolver = build_collect(monkeypatch, captured, [d, r], [g])
        scan_group = ScanComplianceGroupUseCase(FakeGroupRepo([g]), FakeNodeRepo([d, r]), resolver, uc)
        out = await scan_group.execute("g")
        assert out["members"] == 2 and out["scanned"] == 2
        assert {n["hostname"] for n in out["nodes"]} == {"d", "r"}
        # both members produced tagged reports
        assert {rep.os_family for rep in repo.saved} == {"debian", "redhat"}
