from __future__ import annotations
import logging
import uuid
from datetime import datetime

from core.domain.entities import NodeGroup
from core.errors import NotFoundError, ConflictError, ValidationError

logger = logging.getLogger(__name__)


class CreateNodeGroupUseCase:
    def __init__(self, repo, node_repo, wazuh_client, puppet_client):
        self._repo = repo
        self._node_repo = node_repo
        self._wazuh = wazuh_client
        self._puppet = puppet_client

    async def execute(self, data: dict) -> NodeGroup:
        name = data.get("name", "").strip()
        if not name:
            raise ValidationError("name is required")
        existing = await self._repo.find_by_name(name)
        if existing:
            raise ConflictError(f"Node group '{name}' already exists")
        group = NodeGroup(
            id=str(uuid.uuid4()),
            name=name,
            description=data.get("description"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        await self._repo.save(group)
        # Sync to Wazuh and Puppet NC (non-blocking on failure)
        wazuh_ok = True
        puppet_ok = True
        puppet_gid = ""
        try:
            await self._wazuh.create_agent_group(name)
        except Exception as e:
            wazuh_ok = False
            logger.warning("Wazuh group sync failed: %s", e)
        try:
            puppet_gid = await self._puppet.create_node_group(name, data.get("description"))
        except Exception as e:
            puppet_ok = False
            logger.warning("Puppet NC group sync failed: %s", e)
        group.wazuh_synced = wazuh_ok
        group.puppet_synced = puppet_ok
        group.puppet_group_id = puppet_gid or None
        await self._repo.update(group)
        return group


class DeleteNodeGroupUseCase:
    def __init__(self, repo, wazuh_client, puppet_client):
        self._repo = repo
        self._wazuh = wazuh_client
        self._puppet = puppet_client

    async def execute(self, group_id: str) -> dict:
        group = await self._repo.find_by_id(group_id)
        if not group:
            raise NotFoundError(f"Node group '{group_id}' not found")
        # Delete from Puppet NC first, then Wazuh, then DB
        try:
            await self._puppet.delete_node_group(group.puppet_group_id or "")
        except Exception as e:
            logger.warning("Puppet NC delete group failed: %s", e)
        try:
            await self._wazuh.delete_agent_group(group.name)
        except Exception as e:
            logger.warning("Wazuh delete group failed: %s", e)
        await self._repo.delete(group_id)
        return {"message": f"Node group '{group.name}' deleted"}


class ListNodeGroupsUseCase:
    def __init__(self, repo):
        self._repo = repo

    async def execute(self) -> list[NodeGroup]:
        return await self._repo.find_all()


class GetNodeGroupUseCase:
    def __init__(self, repo):
        self._repo = repo

    async def execute(self, gid: str) -> NodeGroup:
        g = await self._repo.find_by_id(gid)
        if not g:
            raise NotFoundError(f"Node group '{gid}' not found")
        return g


class AddNodeToGroupUseCase:
    def __init__(self, repo, node_repo):
        self._repo = repo
        self._node_repo = node_repo

    async def execute(self, group_id: str, node_id: str) -> dict:
        g = await self._repo.find_by_id(group_id)
        if not g:
            raise NotFoundError(f"Node group '{group_id}' not found")
        n = await self._node_repo.find_by_id(node_id)
        if not n:
            raise NotFoundError(f"Node '{node_id}' not found")
        await self._repo.add_node(group_id, node_id)
        return {"message": f"Node '{n.hostname}' added to group '{g.name}'"}


class RemoveNodeFromGroupUseCase:
    def __init__(self, repo, node_repo):
        self._repo = repo
        self._node_repo = node_repo

    async def execute(self, group_id: str, node_id: str) -> dict:
        g = await self._repo.find_by_id(group_id)
        if not g:
            raise NotFoundError(f"Node group '{group_id}' not found")
        await self._repo.remove_node(group_id, node_id)
        return {"message": f"Node removed from group '{g.name}'"}
