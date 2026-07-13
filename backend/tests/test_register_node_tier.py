"""Tier assignment at enrolment: the Add Server form carries an optional
tier_id so a node is classified when it is registered, without a detour
through the Tiers page. Unknown tiers are rejected; omitted → Non-critical."""
from __future__ import annotations

import pytest

from core.domain.entities import (
    CRITICAL_TIER_ID, NON_CRITICAL_TIER_ID, Node, Tier,
)
from core.errors import ValidationError
from modules.nodes.usecases import RegisterNodeUseCase


class FakeNodeRepo:
    def __init__(self):
        self.saved: list[Node] = []
    async def find_by_hostname(self, h): return None
    async def save(self, n): self.saved.append(n)


class FakeSsh:
    async def test_connectivity(self, ip, port, user, key): return True, None
    async def run_command(self, ip, port, user, key, cmd):
        if "os-release" in cmd:
            return 'ID=ubuntu\nID_LIKE=debian\nNAME="Ubuntu"\nVERSION_ID="22.04"\n', "", 0
        return "web-01.sabc.cm", "", 0


class FakeBus:
    def publish(self, *a, **k): pass


class FakeTierRepo:
    def __init__(self):
        self.t = {
            NON_CRITICAL_TIER_ID: Tier(id=NON_CRITICAL_TIER_ID, name="Non-critical", is_system=True),
            CRITICAL_TIER_ID: Tier(id=CRITICAL_TIER_ID, name="Critical",
                                   includes_level_2=True, is_system=True),
        }
    async def find_by_id(self, i): return self.t.get(i)


def build():
    repo = FakeNodeRepo()
    uc = RegisterNodeUseCase(repo, FakeSsh(), FakeBus(), tier_repo=FakeTierRepo())
    return uc, repo


BASE = {"hostname": "web-01", "ip": "10.0.0.5"}


class TestTierAtEnrolment:
    async def test_defaults_to_non_critical_when_omitted(self) -> None:
        uc, repo = build()
        node = await uc.execute(dict(BASE))
        assert node.tier_id == NON_CRITICAL_TIER_ID
        assert repo.saved[0].tier_id == NON_CRITICAL_TIER_ID

    async def test_blank_tier_id_defaults_to_non_critical(self) -> None:
        uc, _ = build()
        node = await uc.execute({**BASE, "tier_id": "  "})
        assert node.tier_id == NON_CRITICAL_TIER_ID

    async def test_assigns_the_picked_tier(self) -> None:
        uc, repo = build()
        node = await uc.execute({**BASE, "tier_id": CRITICAL_TIER_ID})
        assert node.tier_id == CRITICAL_TIER_ID
        assert repo.saved[0].tier_id == CRITICAL_TIER_ID

    async def test_unknown_tier_is_rejected_before_saving(self) -> None:
        uc, repo = build()
        with pytest.raises(ValidationError):
            await uc.execute({**BASE, "tier_id": "tier-ghost"})
        assert repo.saved == []

    async def test_works_without_tier_repo(self) -> None:
        # Back-compat: constructed without a tier repo (no validation possible),
        # the requested tier is still stamped on the node.
        repo = FakeNodeRepo()
        uc = RegisterNodeUseCase(repo, FakeSsh(), FakeBus())
        node = await uc.execute({**BASE, "tier_id": CRITICAL_TIER_ID})
        assert node.tier_id == CRITICAL_TIER_ID
