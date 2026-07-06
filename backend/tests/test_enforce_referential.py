"""Referential enforcement (Task #15): apply sabc_hardening scoped to the
node's tier + OS family so the internal referential fully passes.

The applicable-control resolution reuses the real ScanPlanResolver + tiers, so
these tests also pin that enforce and scan agree on exactly the same control set.
"""
from __future__ import annotations

import pytest

from core.domain.entities import (
    CRITICAL_TIER_ID, NON_CRITICAL_TIER_ID, SABC_BASELINE_PROFILE_ID,
    ComplianceGroup, Job, Node, Profile, ProfileControl, Tier,
)
from core.errors import ValidationError
from modules.compliance.scan_resolver import ScanPlanResolver
from modules.compliance.usecases import EnforceReferentialUseCase


# ── Fakes ─────────────────────────────────────────────────────────────────────

def _c(cid, level, applies="debian;redhat", key=None):
    return ProfileControl(id=cid, profile_id="std", section_id="s", section="S",
                          title=cid, kind="control", control_id=cid,
                          control_key=key, cis_level=level, applies_to=applies)


# c1: L1 both, c2: L1 debian-only, c3: L2 both, c4: L2 redhat-only
CONTROLS = [_c("c1", 1), _c("c2", 1, "debian"), _c("c3", 2), _c("c4", 2, "redhat")]


class FakeProfileRepo:
    def __init__(self):
        self.p = {SABC_BASELINE_PROFILE_ID: Profile(
            id=SABC_BASELINE_PROFILE_ID, name="SABC Baseline",
            version="1.0.0", controls=CONTROLS)}
    async def find_by_id(self, i): return self.p.get(i)
    async def find_all(self): return list(self.p.values())


class FakeTierRepo:
    def __init__(self):
        self.t = {NON_CRITICAL_TIER_ID: Tier(id=NON_CRITICAL_TIER_ID, name="Non-critical", is_system=True),
                  CRITICAL_TIER_ID: Tier(id=CRITICAL_TIER_ID, name="Critical", includes_level_2=True, is_system=True)}
    async def find_by_id(self, i): return self.t.get(i)


class FakeGroupRepo:
    def __init__(self, groups): self.groups = groups
    async def find_by_id(self, i): return next((g for g in self.groups if g.id == i), None)
    async def find_for_node(self, nid): return [g for g in self.groups if nid in g.node_ids]


class FakeNodeRepo:
    def __init__(self, nodes): self.nodes = {n.id: n for n in nodes}
    async def find_by_id(self, i): return self.nodes.get(i)
    async def find_by_hostname(self, h): return next((n for n in self.nodes.values() if n.hostname == h), None)


class FakeStartJob:
    def __init__(self): self.started: list[dict] = []
    async def execute(self, data: dict) -> Job:
        self.started.append(data)
        return Job(id=f"job-{len(self.started)}", type=data["type"],
                   status="pending", node_id=data.get("node_id"),
                   playbook=data.get("playbook"))


class FakeGetGroup:
    """GetNodeGroupUseCase stand-in: returns (group, member_ids)."""
    def __init__(self, groups: dict[str, list[str]]):
        self.groups = groups
    async def execute(self, gid: str):
        members = self.groups.get(gid, [])
        return type("G", (), {"name": f"grp-{gid}"}), members


def node(nid, family, tier=NON_CRITICAL_TIER_ID):
    return Node(id=nid, hostname=nid, ip="10.0.0.9", ssh_user="ansible",
                os_family=family, tier_id=tier)


def build(nodes, groups=None, group_members=None):
    node_repo = FakeNodeRepo(nodes)
    resolver = ScanPlanResolver(node_repo, FakeGroupRepo(groups or []),
                                FakeTierRepo(), FakeProfileRepo(),
                                inspec_dir_for=lambda p: None)
    start = FakeStartJob()
    uc = EnforceReferentialUseCase(
        node_repo=node_repo, start_job_uc=start, scan_resolver=resolver,
        profile_repo=FakeProfileRepo(), module_src="/app/puppet/modules/sabc_hardening",
        get_group_uc=FakeGetGroup(group_members or {}),
    )
    return uc, start


def _controls_of(job: dict) -> set[str]:
    return set(job["extra_vars"]["sabc_controls"])


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSingleNode:
    async def test_non_critical_debian_enforces_l1_debian_only(self) -> None:
        uc, start = build([node("n1", "Debian")])
        out = await uc.execute(node_id="n1")

        assert out["launched"] == 1 and out["skipped"] == 0
        assert len(start.started) == 1
        job = start.started[0]
        assert job["playbook"] == "enforce_referential.yml"
        assert job["node_id"] == "n1"
        assert job["extra_vars"]["sabc_module_src"] == "/app/puppet/modules/sabc_hardening"
        # non-critical (L1) debian → c1, c2 (c3/c4 are L2; c4 is redhat)
        assert _controls_of(job) == {"c1", "c2"}

    async def test_critical_redhat_includes_l2_redhat(self) -> None:
        uc, start = build([node("n1", "RedHat", tier=CRITICAL_TIER_ID)])
        out = await uc.execute(node_id="n1")

        assert out["launched"] == 1
        # critical (L1+L2) redhat → c1, c3, c4 (c2 is debian-only)
        assert _controls_of(start.started[0]) == {"c1", "c3", "c4"}

    async def test_keys_are_sorted_and_deduped(self) -> None:
        uc, start = build([node("n1", "Debian")])
        await uc.execute(node_id="n1")
        keys = start.started[0]["extra_vars"]["sabc_controls"]
        assert keys == sorted(keys)
        assert len(keys) == len(set(keys))


class TestControlKeyMapping:
    async def test_uses_control_key_when_present(self) -> None:
        # control_key overrides control_id for the puppet class name.
        global CONTROLS
        saved = CONTROLS
        try:
            import modules.compliance.usecases as m  # noqa: F401
            # A node whose baseline uses explicit keys.
            controls = [_c("c1", 1, "debian", key="Ensure-Thing_1")]
            repo = FakeProfileRepo()
            repo.p[SABC_BASELINE_PROFILE_ID] = Profile(
                id=SABC_BASELINE_PROFILE_ID, name="B", version="1", controls=controls)
            node_repo = FakeNodeRepo([node("n1", "Debian")])
            resolver = ScanPlanResolver(node_repo, FakeGroupRepo([]), FakeTierRepo(),
                                        repo, inspec_dir_for=lambda p: None)
            start = FakeStartJob()
            uc = EnforceReferentialUseCase(
                node_repo=node_repo, start_job_uc=start, scan_resolver=resolver,
                profile_repo=repo, module_src="/x", get_group_uc=FakeGetGroup({}))
            await uc.execute(node_id="n1")
            # sanitized: lowercase, non-alnum → underscore
            assert _controls_of(start.started[0]) == {"ensure_thing_1"}
        finally:
            CONTROLS = saved


class TestGroup:
    async def test_group_fans_out_per_member(self) -> None:
        d = node("d", "Debian")
        r = node("r", "RedHat", tier=CRITICAL_TIER_ID)
        uc, start = build([d, r], group_members={"g": ["d", "r"]})
        out = await uc.execute(group_id="g")

        assert out["target"]["kind"] == "group"
        assert out["requested"] == 2 and out["launched"] == 2
        by_node = {j["node_id"]: _controls_of(j) for j in start.started}
        assert by_node["d"] == {"c1", "c2"}
        assert by_node["r"] == {"c1", "c3", "c4"}

    async def test_missing_member_is_skipped(self) -> None:
        uc, start = build([node("d", "Debian")], group_members={"g": ["d", "ghost"]})
        out = await uc.execute(group_id="g")
        assert out["launched"] == 1 and out["skipped"] == 1
        assert len(start.started) == 1


class TestValidation:
    async def test_requires_exactly_one_target(self) -> None:
        uc, _ = build([node("n1", "Debian")])
        with pytest.raises(ValidationError):
            await uc.execute()
        with pytest.raises(ValidationError):
            await uc.execute(node_id="n1", group_id="g")

    async def test_unknown_node_raises(self) -> None:
        from core.errors import NotFoundError
        uc, _ = build([node("n1", "Debian")])
        with pytest.raises(NotFoundError):
            await uc.execute(node_id="ghost")
