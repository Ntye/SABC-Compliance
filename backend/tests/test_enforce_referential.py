"""Referential enforcement (Task #15): apply sabc_hardening scoped to the
node's tier + OS family so the internal referential fully passes.

The applicable-control resolution reuses the real ScanPlanResolver + tiers, so
these tests also pin that enforce and scan agree on exactly the same control set.
"""
from __future__ import annotations

import pytest

from core.domain.entities import (
    TIER_2_ID, TIER_1_ID, SABC_BASELINE_PROFILE_ID,
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


def node(nid, family, tier=TIER_1_ID):
    return Node(id=nid, hostname=nid, ip="10.0.0.9", ssh_user="ansible",
                os_family=family, tier_id=tier)


class FakeNotificationRepo:
    def __init__(self): self.saved = []
    async def save(self, n): self.saved.append(n)


class FakeCollect:
    """CollectNodeComplianceUseCase stand-in for the post-enforcement scan."""
    def __init__(self, fail=False):
        self.fail = fail
        self.calls: list[str] = []
    async def execute(self, node_id):
        self.calls.append(node_id)
        if self.fail:
            raise RuntimeError("scan engine unreachable")
        return {"node_id": node_id, "collected": [
            {"source": "scan", "score": 94},
            {"source": "puppet", "score": 100},
        ]}


class FakeComplianceRepo:
    """Records the enforcement suppression windows opened and closed."""
    def __init__(self):
        self.saved, self.updated = [], []
    async def save_remediation(self, rem): self.saved.append(rem)
    async def update_remediation(self, rem): self.updated.append(rem)


def build(nodes, groups=None, group_members=None, notification_repo=None,
          collect_uc=None, compliance_repo=None):
    node_repo = FakeNodeRepo(nodes)
    resolver = ScanPlanResolver(node_repo, FakeGroupRepo(groups or []),
                                FakeTierRepo(), FakeProfileRepo(),
                                inspec_dir_for=lambda p: None)
    start = FakeStartJob()
    uc = EnforceReferentialUseCase(
        node_repo=node_repo, start_job_uc=start, scan_resolver=resolver,
        profile_repo=FakeProfileRepo(), module_src="/app/puppet/modules/sabc_hardening",
        get_group_uc=FakeGetGroup(group_members or {}),
        notification_repo=notification_repo, collect_uc=collect_uc,
        compliance_repo=compliance_repo,
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
        uc, start = build([node("n1", "RedHat", tier=TIER_2_ID)])
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
        r = node("r", "RedHat", tier=TIER_2_ID)
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


class TestTiersPageNotificationChain:
    """Enforcement launched from the Tiers page (notify_on_complete): the
    finished job records a platform notification, then chains a verification
    scan whose outcome is notified too."""

    def _built(self, collect=None):
        notif = FakeNotificationRepo()
        collect = collect or FakeCollect()
        uc, start = build([node("n1", "Debian")],
                          notification_repo=notif, collect_uc=collect)
        return uc, start, notif, collect

    async def test_on_complete_attached_only_when_requested(self) -> None:
        uc, start, _, _ = self._built()
        await uc.execute(node_id="n1")
        assert start.started[0]["on_complete"] is None
        await uc.execute(node_id="n1", notify_on_complete=True)
        attached = start.started[1]["on_complete"]
        assert attached is not None and attached.__func__ is uc._on_complete.__func__

    async def test_success_notifies_then_scans_then_notifies(self) -> None:
        uc, _, notif, collect = self._built()
        job = Job(id="j1", status="success", exit_code=0, node_id="n1")
        await uc._on_complete(job, node("n1", "Debian"))

        assert collect.calls == ["n1"]
        assert [n.kind for n in notif.saved] == ["enforcement", "scan"]
        assert all(n.severity == "success" for n in notif.saved)
        assert notif.saved[0].job_id == "j1" and notif.saved[0].node_id == "n1"
        assert "94%" in notif.saved[1].message  # primary (non-puppet) report score

    async def test_failed_job_notifies_error_and_skips_scan(self) -> None:
        uc, _, notif, collect = self._built()
        job = Job(id="j1", status="failed", exit_code=2, node_id="n1")
        await uc._on_complete(job, node("n1", "Debian"))

        assert collect.calls == []
        assert len(notif.saved) == 1
        assert notif.saved[0].kind == "enforcement" and notif.saved[0].severity == "error"

    async def test_scan_failure_notifies_error_without_raising(self) -> None:
        uc, _, notif, _ = self._built(collect=FakeCollect(fail=True))
        job = Job(id="j1", status="success", exit_code=0, node_id="n1")
        await uc._on_complete(job, node("n1", "Debian"))  # must not raise

        assert [n.kind for n in notif.saved] == ["enforcement", "scan"]
        assert notif.saved[1].severity == "error"
        assert "unreachable" in notif.saved[1].message


class TestSuppressionWindow:
    """An enforcement job's own writes on the node (puppet apply rewriting
    pam.d, sshd_config, sudoers…) must be suppressed by detection rule (a):
    the use case opens a pending RemediationEvent before the job launches and
    closes it when the job reaches a terminal state."""

    async def test_window_opened_before_launch_and_closed_on_success(self) -> None:
        comp = FakeComplianceRepo()
        uc, start = build([node("n1", "Debian")], compliance_repo=comp)

        result = await uc.execute(node_id="n1")

        assert len(comp.saved) == 1
        rem = comp.saved[0]
        assert rem.node_id == "n1" and rem.outcome == "pending"
        assert comp.updated == []                       # still open while job runs

        cb = start.started[0]["on_complete"]
        assert cb is not None
        await cb(Job(id="j1", status="success", exit_code=0, node_id="n1"), None)

        assert len(comp.updated) == 1
        closed = comp.updated[0]
        assert closed.outcome == "success" and closed.completed_at is not None
        assert closed.resources_fixed == result["jobs"][0]["controls"]

    async def test_window_closed_failed_on_job_failure(self) -> None:
        comp = FakeComplianceRepo()
        uc, start = build([node("n1", "Debian")], compliance_repo=comp)
        await uc.execute(node_id="n1")

        await start.started[0]["on_complete"](
            Job(id="j1", status="failed", exit_code=2, node_id="n1"), None)

        assert comp.updated[0].outcome == "failed"
        assert comp.updated[0].resources_fixed == 0

    async def test_no_window_when_caller_manages_its_own(self) -> None:
        # The closed loop's scoped path opens its own window and passes
        # on_complete to close it — a second one here would be a duplicate.
        comp = FakeComplianceRepo()
        uc, start = build([node("n1", "Debian")], compliance_repo=comp)

        async def caller_cb(job, n): ...
        await uc.execute(node_id="n1", on_complete=caller_cb)

        assert comp.saved == []
        assert start.started[0]["on_complete"] is caller_cb

    async def test_window_close_chains_the_notify_callback(self) -> None:
        comp = FakeComplianceRepo()
        notif = FakeNotificationRepo()
        uc, start = build([node("n1", "Debian")],
                          compliance_repo=comp, notification_repo=notif)
        await uc.execute(node_id="n1", notify_on_complete=True)

        await start.started[0]["on_complete"](
            Job(id="j1", status="failed", exit_code=2, node_id="n1"), None)

        assert comp.updated[0].outcome == "failed"      # window closed first
        assert [n.kind for n in notif.saved] == ["enforcement"]  # then notified


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
