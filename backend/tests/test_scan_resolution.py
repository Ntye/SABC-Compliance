"""Group -> profiles -> members -> tier -> family scan resolution (Section 6)."""
from __future__ import annotations

import pytest

from core.domain.entities import (
    TIER_1_ID, TIER_2_ID, SABC_BASELINE_PROFILE_ID,
    ComplianceGroup, Node, Profile, ProfileControl, Tier,
)
from modules.compliance.scan_resolver import ScanPlanResolver


# A control matrix spanning both levels and both family scopes.
def _c(cid, level, applies):
    return ProfileControl(
        id=cid, profile_id="std", section_id="s", section="S", title=cid,
        kind="control", control_id=cid, cis_level=level, applies_to=applies,
    )


CONTROLS = [
    _c("c1", 1, "debian;redhat"),   # L1 both
    _c("c2", 1, "debian"),          # L1 debian only
    _c("c3", 2, "debian;redhat"),   # L2 both
    _c("c4", 2, "redhat"),          # L2 redhat only
]


class FakeProfileRepo:
    def __init__(self):
        self.p = {
            "std": Profile(id="std", name="Standard X", version="2.1.0", controls=CONTROLS),
            SABC_BASELINE_PROFILE_ID: Profile(
                id=SABC_BASELINE_PROFILE_ID, name="SABC Baseline", version="1.0.0",
                source="builtin", is_system=True, controls=CONTROLS),
        }
    async def find_by_id(self, i): return self.p.get(i)
    async def find_all(self): return list(self.p.values())


class FakeTierRepo:
    def __init__(self):
        self.t = {
            TIER_1_ID: Tier(id=TIER_1_ID, name="Tier 1",
                                       includes_level_2=False, is_system=True),
            TIER_2_ID: Tier(id=TIER_2_ID, name="Tier 2",
                                   includes_level_2=True, is_system=True),
        }
    async def find_by_id(self, i): return self.t.get(i)


class FakeGroupRepo:
    def __init__(self, groups): self.groups = groups
    async def find_for_node(self, nid):
        return [g for g in self.groups if nid in g.node_ids]


class FakeNodeRepo:
    def __init__(self, nodes): self.nodes = {n.id: n for n in nodes}
    async def find_by_id(self, i): return self.nodes.get(i)


def node(nid, family, tier=TIER_1_ID):
    return Node(id=nid, hostname=nid, ip="1.1.1.1", os_family=family, tier_id=tier)


def resolver(nodes, groups):
    return ScanPlanResolver(
        FakeNodeRepo(nodes), FakeGroupRepo(groups), FakeTierRepo(), FakeProfileRepo(),
        inspec_dir_for=lambda p: f"/scan/{p.id}",
    )


# ── Family narrowing ──────────────────────────────────────────────────────────

class TestFamily:
    async def test_debian_noncritical_gets_l1_debian_controls(self) -> None:
        n = node("n1", "Debian")
        g = ComplianceGroup(id="g", name="G", profile_ids=["std"], node_ids=["n1"])
        plan = await resolver([n], [g]).for_node(n)
        assert plan.os_family == "debian" and plan.tier_name == "Tier 1"
        assert set(plan.specs[0].applicable_control_ids) == {"c1", "c2"}  # L1, debian

    async def test_redhat_noncritical_excludes_debian_only_control(self) -> None:
        n = node("n1", "RedHat")
        g = ComplianceGroup(id="g", name="G", profile_ids=["std"], node_ids=["n1"])
        plan = await resolver([n], [g]).for_node(n)
        assert set(plan.specs[0].applicable_control_ids) == {"c1"}  # c2 is debian-only

    async def test_facter_family_form_is_normalised(self) -> None:
        # os_family arrives as facter 'RedHat'/'Debian'; resolver normalises it.
        n = node("n1", "RedHat")
        g = ComplianceGroup(id="g", name="G", profile_ids=["std"], node_ids=["n1"])
        plan = await resolver([n], [g]).for_node(n)
        assert plan.os_family == "redhat"


# ── Tier narrowing ────────────────────────────────────────────────────────────

class TestTier:
    async def test_critical_debian_adds_level_2_both_family_control(self) -> None:
        n = node("n1", "Debian", tier=TIER_2_ID)
        g = ComplianceGroup(id="g", name="G", profile_ids=["std"], node_ids=["n1"])
        plan = await resolver([n], [g]).for_node(n)
        # L1 debian (c1,c2) + L2 both (c3); c4 is redhat-only
        assert set(plan.specs[0].applicable_control_ids) == {"c1", "c2", "c3"}

    async def test_critical_redhat_gets_l2_redhat_control(self) -> None:
        n = node("n1", "RedHat", tier=TIER_2_ID)
        g = ComplianceGroup(id="g", name="G", profile_ids=["std"], node_ids=["n1"])
        plan = await resolver([n], [g]).for_node(n)
        assert set(plan.specs[0].applicable_control_ids) == {"c1", "c3", "c4"}


# ── Group -> profiles -> members ──────────────────────────────────────────────

class TestGroups:
    async def test_records_profile_version_and_group_provenance(self) -> None:
        n = node("n1", "Debian")
        g = ComplianceGroup(id="g1", name="Prod", profile_ids=["std"], node_ids=["n1"])
        plan = await resolver([n], [g]).for_node(n)
        spec = plan.specs[0]
        assert spec.profile_version == "2.1.0"
        assert spec.compliance_group_id == "g1" and spec.compliance_group_name == "Prod"
        assert spec.inspec_dir == "/scan/std"

    async def test_node_in_multiple_groups_unions_profiles(self) -> None:
        n = node("n1", "Debian")
        g1 = ComplianceGroup(id="g1", name="A", profile_ids=["std"], node_ids=["n1"])
        g2 = ComplianceGroup(id="g2", name="B", profile_ids=[SABC_BASELINE_PROFILE_ID], node_ids=["n1"])
        plan = await resolver([n], [g1, g2]).for_node(n)
        assert {s.profile_id for s in plan.specs} == {"std", SABC_BASELINE_PROFILE_ID}

    async def test_node_in_no_group_falls_back_to_baseline(self) -> None:
        n = node("n1", "Debian")
        plan = await resolver([n], []).for_node(n)
        assert len(plan.specs) == 1
        assert plan.specs[0].profile_id == SABC_BASELINE_PROFILE_ID
        assert plan.specs[0].compliance_group_id is None   # no group provenance

    async def test_for_group_yields_plan_per_member(self) -> None:
        d = node("d", "Debian")
        r = node("r", "RedHat", tier=TIER_2_ID)
        g = ComplianceGroup(id="g", name="Mixed", profile_ids=["std"], node_ids=["d", "r"])
        plans = await resolver([d, r], [g]).for_group(g)
        by_node = {p.node_id: p for p in plans}
        assert set(by_node["d"].specs[0].applicable_control_ids) == {"c1", "c2"}
        assert set(by_node["r"].specs[0].applicable_control_ids) == {"c1", "c3", "c4"}
