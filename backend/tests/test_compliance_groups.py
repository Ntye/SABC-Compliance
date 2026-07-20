"""Compliance node group CRUD (Section 5) — platform-only, ref-validated."""
from __future__ import annotations

import pytest

from core.domain.entities import ComplianceGroup, Node, Profile
from core.errors import ConflictError, NotFoundError, ValidationError
from modules.compliance_groups.usecases import (
    AddGroupMemberUseCase, CreateComplianceGroupUseCase,
    RemoveGroupMemberUseCase, UpdateComplianceGroupUseCase,
)


class FakeGroupRepo:
    def __init__(self): self.g = {}
    async def save(self, x): self.g[x.id] = x
    async def find_by_id(self, i): return self.g.get(i)
    async def find_by_name(self, n): return next((x for x in self.g.values() if x.name == n), None)
    async def find_all(self): return list(self.g.values())
    async def find_for_node(self, nid): return [x for x in self.g.values() if nid in x.node_ids]
    async def update(self, x): self.g[x.id] = x
    async def delete(self, i): self.g.pop(i, None)


class FakeProfileRepo:
    def __init__(self, ids): self.ids = set(ids)
    async def find_by_id(self, i): return Profile(id=i, name=i) if i in self.ids else None


class FakeNodeRepo:
    def __init__(self, ids): self.ids = set(ids)
    async def find_by_id(self, i):
        return Node(id=i, hostname=i, ip="1.1.1.1") if i in self.ids else None


@pytest.fixture()
def repos():
    return FakeGroupRepo(), FakeProfileRepo(["p1", "p2"]), FakeNodeRepo(["n1", "n2", "n3"])


class TestCreate:
    async def test_create_with_valid_refs(self, repos) -> None:
        gr, pr, nr = repos
        uc = CreateComplianceGroupUseCase(gr, pr, nr)
        g = await uc.execute({"name": "Prod", "profile_ids": ["p1"], "node_ids": ["n1", "n2"]})
        assert g.name == "Prod" and g.profile_ids == ["p1"] and set(g.node_ids) == {"n1", "n2"}

    async def test_reject_unknown_profile(self, repos) -> None:
        gr, pr, nr = repos
        uc = CreateComplianceGroupUseCase(gr, pr, nr)
        with pytest.raises(ValidationError):
            await uc.execute({"name": "X", "profile_ids": ["ghost"]})

    async def test_reject_unknown_node(self, repos) -> None:
        gr, pr, nr = repos
        uc = CreateComplianceGroupUseCase(gr, pr, nr)
        with pytest.raises(ValidationError):
            await uc.execute({"name": "X", "node_ids": ["ghost"]})

    async def test_reject_duplicate_name(self, repos) -> None:
        gr, pr, nr = repos
        uc = CreateComplianceGroupUseCase(gr, pr, nr)
        await uc.execute({"name": "Dup"})
        with pytest.raises(ConflictError):
            await uc.execute({"name": "Dup"})

    async def test_dedups_ids(self, repos) -> None:
        gr, pr, nr = repos
        uc = CreateComplianceGroupUseCase(gr, pr, nr)
        g = await uc.execute({"name": "D", "node_ids": ["n1", "n1", "n2"]})
        assert g.node_ids == ["n1", "n2"]


class TestMembership:
    async def test_add_and_remove_member(self, repos) -> None:
        gr, pr, nr = repos
        await CreateComplianceGroupUseCase(gr, pr, nr).execute({"name": "G", "node_ids": ["n1"]})
        gid = (await gr.find_by_name("G")).id
        g = await AddGroupMemberUseCase(gr, nr).execute(gid, "n2")
        assert set(g.node_ids) == {"n1", "n2"}
        g = await RemoveGroupMemberUseCase(gr).execute(gid, "n1")
        assert g.node_ids == ["n2"]

    async def test_node_in_multiple_groups(self, repos) -> None:
        gr, pr, nr = repos
        c = CreateComplianceGroupUseCase(gr, pr, nr)
        await c.execute({"name": "A", "node_ids": ["n1"]})
        await c.execute({"name": "B", "node_ids": ["n1"]})
        groups = await gr.find_for_node("n1")
        assert {g.name for g in groups} == {"A", "B"}

    async def test_add_member_unknown_node_404(self, repos) -> None:
        gr, pr, nr = repos
        await CreateComplianceGroupUseCase(gr, pr, nr).execute({"name": "G"})
        gid = (await gr.find_by_name("G")).id
        with pytest.raises(NotFoundError):
            await AddGroupMemberUseCase(gr, nr).execute(gid, "ghost")


class TestUpdate:
    async def test_update_profiles_and_members(self, repos) -> None:
        gr, pr, nr = repos
        await CreateComplianceGroupUseCase(gr, pr, nr).execute({"name": "G"})
        gid = (await gr.find_by_name("G")).id
        g = await UpdateComplianceGroupUseCase(gr, pr, nr).execute(
            gid, {"profile_ids": ["p1", "p2"], "node_ids": ["n3"]})
        assert set(g.profile_ids) == {"p1", "p2"} and g.node_ids == ["n3"]
