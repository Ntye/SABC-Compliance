"""
Compliance node groups (Section 5) — a PLATFORM concept, entirely separate from
Puppet node groups.

A compliance group binds a set of PROFILES (the standards its members are scanned
against) to a set of NODE members. A node may belong to several compliance
groups (and is scanned against each group's bound profiles). These use cases
NEVER call the Puppet Node Classifier API — they are platform-only.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from core.domain.entities import ComplianceGroup
from core.domain.interfaces import (
    IComplianceGroupRepository, INodeRepository, IProfileRepository,
)
from core.errors import ConflictError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class _RefValidationMixin:
    _profiles: IProfileRepository
    _nodes: INodeRepository

    async def _validate_refs(self, profile_ids: list[str], node_ids: list[str]) -> None:
        for pid in profile_ids or []:
            if not await self._profiles.find_by_id(pid):
                raise ValidationError(f"Profile '{pid}' does not exist.")
        for nid in node_ids or []:
            if not await self._nodes.find_by_id(nid):
                raise ValidationError(f"Node '{nid}' does not exist.")


class CreateComplianceGroupUseCase(_RefValidationMixin):
    def __init__(self, repo: IComplianceGroupRepository,
                 profile_repo: IProfileRepository, node_repo: INodeRepository) -> None:
        self._repo = repo
        self._profiles = profile_repo
        self._nodes = node_repo

    async def execute(self, data: dict) -> ComplianceGroup:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("Compliance group name is required.")
        if await self._repo.find_by_name(name):
            raise ConflictError(f"A compliance group named '{name}' already exists.")
        profile_ids = list(dict.fromkeys(data.get("profile_ids") or []))
        node_ids = list(dict.fromkeys(data.get("node_ids") or []))
        await self._validate_refs(profile_ids, node_ids)
        now = datetime.utcnow()
        group = ComplianceGroup(
            id=str(uuid.uuid4()),
            name=name,
            description=(data.get("description") or None),
            profile_ids=profile_ids,
            node_ids=node_ids,
            created_at=now,
            updated_at=now,
        )
        await self._repo.save(group)
        logger.info("Created compliance group '%s' (%d profiles, %d members)",
                    name, len(profile_ids), len(node_ids))
        return group


class ListComplianceGroupsUseCase:
    def __init__(self, repo: IComplianceGroupRepository) -> None:
        self._repo = repo

    async def execute(self) -> list[ComplianceGroup]:
        return await self._repo.find_all()


class GetComplianceGroupUseCase:
    def __init__(self, repo: IComplianceGroupRepository) -> None:
        self._repo = repo

    async def execute(self, group_id: str) -> ComplianceGroup:
        g = await self._repo.find_by_id(group_id)
        if not g:
            raise NotFoundError(f"Compliance group '{group_id}' not found")
        return g


class UpdateComplianceGroupUseCase(_RefValidationMixin):
    def __init__(self, repo: IComplianceGroupRepository,
                 profile_repo: IProfileRepository, node_repo: INodeRepository) -> None:
        self._repo = repo
        self._profiles = profile_repo
        self._nodes = node_repo

    async def execute(self, group_id: str, data: dict) -> ComplianceGroup:
        g = await self._repo.find_by_id(group_id)
        if not g:
            raise NotFoundError(f"Compliance group '{group_id}' not found")
        if "name" in data and data["name"]:
            name = str(data["name"]).strip()
            clash = await self._repo.find_by_name(name)
            if clash and clash.id != group_id:
                raise ConflictError(f"A compliance group named '{name}' already exists.")
            g.name = name
        if "description" in data:
            g.description = data["description"] or None
        if "profile_ids" in data and data["profile_ids"] is not None:
            pids = list(dict.fromkeys(data["profile_ids"]))
            await self._validate_refs(pids, [])
            g.profile_ids = pids
        if "node_ids" in data and data["node_ids"] is not None:
            nids = list(dict.fromkeys(data["node_ids"]))
            await self._validate_refs([], nids)
            g.node_ids = nids
        g.updated_at = datetime.utcnow()
        await self._repo.update(g)
        return await self._repo.find_by_id(group_id)


class DeleteComplianceGroupUseCase:
    def __init__(self, repo: IComplianceGroupRepository) -> None:
        self._repo = repo

    async def execute(self, group_id: str) -> dict:
        g = await self._repo.find_by_id(group_id)
        if not g:
            raise NotFoundError(f"Compliance group '{group_id}' not found")
        await self._repo.delete(group_id)
        return {"message": f"Compliance group '{g.name}' deleted"}


class AddGroupMemberUseCase:
    def __init__(self, repo: IComplianceGroupRepository, node_repo: INodeRepository) -> None:
        self._repo = repo
        self._nodes = node_repo

    async def execute(self, group_id: str, node_id: str) -> ComplianceGroup:
        g = await self._repo.find_by_id(group_id)
        if not g:
            raise NotFoundError(f"Compliance group '{group_id}' not found")
        if not await self._nodes.find_by_id(node_id):
            raise NotFoundError(f"Node '{node_id}' not found")
        if node_id not in g.node_ids:
            g.node_ids.append(node_id)
            g.updated_at = datetime.utcnow()
            await self._repo.update(g)
        return await self._repo.find_by_id(group_id)


class RemoveGroupMemberUseCase:
    def __init__(self, repo: IComplianceGroupRepository) -> None:
        self._repo = repo

    async def execute(self, group_id: str, node_id: str) -> ComplianceGroup:
        g = await self._repo.find_by_id(group_id)
        if not g:
            raise NotFoundError(f"Compliance group '{group_id}' not found")
        if node_id in g.node_ids:
            g.node_ids = [n for n in g.node_ids if n != node_id]
            g.updated_at = datetime.utcnow()
            await self._repo.update(g)
        return await self._repo.find_by_id(group_id)
