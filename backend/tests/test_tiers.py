"""Tier in-scope resolution (Section 4), including custom 'Tier 1.5'."""
from __future__ import annotations

import pytest

from core.domain.entities import (
    CRITICAL_TIER_ID, NON_CRITICAL_TIER_ID, Profile, ProfileControl, Tier,
)
from core.errors import ForbiddenError, ValidationError
from modules.tiers.usecases import (
    CreateTierUseCase, DeleteTierUseCase, SeedSystemTiersUseCase,
    UpdateTierUseCase, applicable_controls, control_is_applicable,
)


def ctl(cid, level, status="active") -> ProfileControl:
    return ProfileControl(
        id=cid, profile_id="p", section_id="s", section="S", title=cid,
        kind="control", control_id=cid, cis_level=level, status=status,
    )


# A mixed-level control set: 3 level-1, 3 level-2.
CONTROLS = [
    ctl("L1.a", 1), ctl("L1.b", 1), ctl("L1.c", 1),
    ctl("L2.a", 2), ctl("L2.b", 2), ctl("L2.c", 2),
]


def tier(**kw) -> Tier:
    return Tier(id=kw.get("id", "t"), name=kw.get("name", "T"),
                includes_level_2=kw.get("includes_level_2", False),
                is_system=kw.get("is_system", False),
                extra_control_ids=kw.get("extra_control_ids", []))


# ── Pure resolution ───────────────────────────────────────────────────────────

class TestResolution:
    def test_non_critical_gets_level_1_only(self) -> None:
        t = tier(includes_level_2=False)
        got = {c.control_id for c in applicable_controls(CONTROLS, t)}
        assert got == {"L1.a", "L1.b", "L1.c"}

    def test_critical_gets_level_1_and_2(self) -> None:
        t = tier(includes_level_2=True)
        got = {c.control_id for c in applicable_controls(CONTROLS, t)}
        assert got == {"L1.a", "L1.b", "L1.c", "L2.a", "L2.b", "L2.c"}

    def test_custom_1_5_gets_level_1_plus_selected_l2(self) -> None:
        # "Tier 1.5": all Level 1 + only the two chosen Level-2 controls.
        t = tier(includes_level_2=False, extra_control_ids=["L2.a", "L2.c"])
        got = {c.control_id for c in applicable_controls(CONTROLS, t)}
        assert got == {"L1.a", "L1.b", "L1.c", "L2.a", "L2.c"}
        assert "L2.b" not in got

    def test_blank_level_treated_as_1(self) -> None:
        c = ctl("X", 0)  # blank => 1
        assert control_is_applicable(c, tier(includes_level_2=False))

    def test_retired_controls_excluded(self) -> None:
        controls = CONTROLS + [ctl("L1.dead", 1, status="retired")]
        got = {c.control_id for c in applicable_controls(controls, tier())}
        assert "L1.dead" not in got


# ── System tier seeding ───────────────────────────────────────────────────────

class FakeTierRepo:
    def __init__(self) -> None:
        self.tiers: dict[str, Tier] = {}

    async def save(self, t): self.tiers[t.id] = t
    async def find_by_id(self, i): return self.tiers.get(i)
    async def find_by_name(self, n): return next((t for t in self.tiers.values() if t.name == n), None)
    async def find_all(self): return list(self.tiers.values())
    async def update(self, t): self.tiers[t.id] = t
    async def delete(self, i): self.tiers.pop(i, None)


class FakeProfileRepo:
    def __init__(self, controls): self._controls = controls
    async def find_all(self):
        return [Profile(id="p", name="P", controls=self._controls)]


@pytest.fixture()
def seeded_repo():
    return FakeTierRepo()


class TestSeeding:
    async def test_seeds_two_system_tiers_idempotently(self, seeded_repo) -> None:
        uc = SeedSystemTiersUseCase(seeded_repo)
        assert await uc.execute() == 2
        assert await uc.execute() == 0  # idempotent
        nc = await seeded_repo.find_by_id(NON_CRITICAL_TIER_ID)
        cr = await seeded_repo.find_by_id(CRITICAL_TIER_ID)
        assert nc.is_system and not nc.includes_level_2
        assert cr.is_system and cr.includes_level_2


# ── Custom tier validation (extra controls must be real Level 2) ──────────────

class TestCustomTierValidation:
    async def test_create_rejects_non_level2_extra_control(self, seeded_repo) -> None:
        profiles = FakeProfileRepo(CONTROLS)
        uc = CreateTierUseCase(seeded_repo, profiles)
        with pytest.raises(ValidationError):
            # L1.a is a Level-1 control — cannot be a custom-tier extra.
            await uc.execute({"name": "Bad", "extra_control_ids": ["L1.a"]})

    async def test_create_rejects_unknown_control(self, seeded_repo) -> None:
        uc = CreateTierUseCase(seeded_repo, FakeProfileRepo(CONTROLS))
        with pytest.raises(ValidationError):
            await uc.execute({"name": "Bad", "extra_control_ids": ["NOPE"]})

    async def test_create_accepts_real_level2_extra(self, seeded_repo) -> None:
        uc = CreateTierUseCase(seeded_repo, FakeProfileRepo(CONTROLS))
        t = await uc.execute({"name": "Tier 1.5", "extra_control_ids": ["L2.a"]},
                             created_by="alice")
        assert t.extra_control_ids == ["L2.a"] and t.created_by == "alice"
        assert not t.is_system

    async def test_update_system_tier_forbidden(self, seeded_repo) -> None:
        await SeedSystemTiersUseCase(seeded_repo).execute()
        uc = UpdateTierUseCase(seeded_repo, FakeProfileRepo(CONTROLS))
        with pytest.raises(ForbiddenError):
            await uc.execute(NON_CRITICAL_TIER_ID, {"includes_level_2": True})

    async def test_delete_system_tier_forbidden(self, seeded_repo) -> None:
        await SeedSystemTiersUseCase(seeded_repo).execute()

        class _Nodes:
            async def find_all(self, f): return []
        uc = DeleteTierUseCase(seeded_repo, _Nodes())
        with pytest.raises(ForbiddenError):
            await uc.execute(CRITICAL_TIER_ID)
