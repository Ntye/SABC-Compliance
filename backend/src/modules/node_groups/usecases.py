from __future__ import annotations
import logging
import re
import uuid
from datetime import datetime

from core.domain.entities import NodeGroup
from core.errors import NotFoundError, ConflictError, ValidationError

logger = logging.getLogger(__name__)

# Facts exposed to the rule builder, mapped to Node attributes.
FACT_ATTRS = {
    "hostname": "hostname",
    "ip": "ip",
    "fqdn": "fqdn",
    "os_family": "os_family",
    "os_name": "os_name",
    "os_version": "os_version",
    "status": "status",
    "tags": "tags",
    "puppet_enrolled": "puppet_enrolled",
    "wazuh_enrolled": "wazuh_enrolled",
}

VALID_OPERATORS = {"=", "!=", "~", ">", ">=", "<", "<="}


def _node_value(node, fact: str):
    attr = FACT_ATTRS.get(fact)
    if not attr:
        return None
    return getattr(node, attr, None)


def _cmp(actual, op: str, value: str) -> bool:
    if isinstance(actual, bool):
        want = str(value).strip().lower() in ("true", "1", "yes")
        return (actual == want) if op == "=" else (actual != want) if op == "!=" else False
    if isinstance(actual, (list, tuple)):
        joined = [str(x).lower() for x in actual]
        v = str(value).lower()
        if op == "=":
            return v in joined
        if op == "!=":
            return v not in joined
        if op == "~":
            return any(re.search(value, str(x), re.IGNORECASE) for x in actual)
        return False
    a = "" if actual is None else str(actual)
    if op == "=":
        return a.lower() == str(value).lower()
    if op == "!=":
        return a.lower() != str(value).lower()
    if op == "~":
        try:
            return bool(re.search(value, a, re.IGNORECASE))
        except re.error:
            return value.lower() in a.lower()
    # numeric comparisons fall back to lexical when non-numeric
    try:
        an, vn = float(a), float(value)
    except (TypeError, ValueError):
        an, vn = a, str(value)
    if op == ">":
        return an > vn
    if op == ">=":
        return an >= vn
    if op == "<":
        return an < vn
    if op == "<=":
        return an <= vn
    return False


def node_matches(node, rules: list[dict], match_type: str) -> bool:
    if not rules:
        return False
    checks = [_cmp(_node_value(node, r.get("fact", "")), r.get("operator", "="), r.get("value", ""))
              for r in rules]
    return all(checks) if (match_type or "all") == "all" else any(checks)


def _certname(node) -> str:
    return node.fqdn or node.hostname


async def resolve_matching(group: NodeGroup, node_repo) -> dict:
    """Return {ids, hostnames, pinned_certnames} for pinned ∪ rule-matched nodes."""
    all_nodes = await node_repo.find_all({})
    pinned_set = set(group.node_ids or [])
    matched_ids, hostnames, pinned_certs = set(), [], []
    for n in all_nodes:
        is_pinned = n.id in pinned_set
        is_rule = node_matches(n, group.rules, group.match_type)
        if is_pinned:
            pinned_certs.append(_certname(n))
        if is_pinned or is_rule:
            matched_ids.add(n.id)
            hostnames.append(n.hostname)
    return {"ids": list(matched_ids), "hostnames": hostnames, "pinned_certnames": pinned_certs}


def _validate(data: dict) -> None:
    for r in data.get("rules") or []:
        if r.get("fact") not in FACT_ATTRS:
            raise ValidationError(f"Unknown fact '{r.get('fact')}'")
        if r.get("operator") not in VALID_OPERATORS:
            raise ValidationError(f"Invalid operator '{r.get('operator')}'")
    if (data.get("match_type") or "all") not in ("all", "any"):
        raise ValidationError("match_type must be 'all' or 'any'")


class CreateNodeGroupUseCase:
    def __init__(self, repo, node_repo, wazuh_client, puppet_client):
        self._repo = repo
        self._node_repo = node_repo
        self._wazuh = wazuh_client
        self._puppet = puppet_client

    async def execute(self, data: dict) -> NodeGroup:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("name is required")
        if await self._repo.find_by_name(name):
            raise ConflictError(f"Node group '{name}' already exists")
        _validate(data)
        now = datetime.utcnow()
        group = NodeGroup(
            id=str(uuid.uuid4()),
            name=name,
            description=data.get("description"),
            parent=data.get("parent") or "All Nodes",
            environment=data.get("environment") or "production",
            is_environment_group=bool(data.get("is_environment_group")),
            match_type=data.get("match_type") or "all",
            rules=data.get("rules") or [],
            node_ids=[],
            created_at=now,
            updated_at=now,
        )
        await self._repo.save(group)
        # Pin nodes selected during creation
        for nid in (data.get("node_ids") or []):
            await self._repo.add_node(group.id, nid)
        group.node_ids = list(data.get("node_ids") or [])
        await self._sync(group, parent_id=await self._parent_id(group.parent))
        return group

    async def _parent_id(self, parent_name: str):
        if not parent_name or parent_name == "All Nodes":
            return None
        parent = await self._repo.find_by_name(parent_name)
        return parent.puppet_group_id if parent else None

    async def _sync(self, group: NodeGroup, parent_id=None) -> None:
        resolved = await resolve_matching(group, self._node_repo)
        wazuh_ok = puppet_ok = True
        puppet_gid = group.puppet_group_id or ""
        try:
            await self._wazuh.create_agent_group(group.name)
            await self._wazuh.assign_agents_to_group(group.name, resolved["hostnames"])
        except Exception as e:
            wazuh_ok = False
            logger.warning("Wazuh group sync failed: %s", e)
        try:
            puppet_gid = await self._puppet.create_node_group(
                group.name, group.description,
                environment=group.environment, parent_id=parent_id,
                match_type=group.match_type, rules=group.rules,
                pinned_certnames=resolved["pinned_certnames"],
            )
        except Exception as e:
            puppet_ok = False
            logger.warning("Puppet NC group sync failed: %s", e)
        group.wazuh_synced = wazuh_ok
        group.puppet_synced = puppet_ok
        group.puppet_group_id = puppet_gid or None
        group.updated_at = datetime.utcnow()
        await self._repo.update(group)


class UpdateNodeGroupUseCase:
    def __init__(self, repo, node_repo, wazuh_client, puppet_client):
        self._repo = repo
        self._node_repo = node_repo
        self._wazuh = wazuh_client
        self._puppet = puppet_client

    async def execute(self, group_id: str, data: dict) -> NodeGroup:
        group = await self._repo.find_by_id(group_id)
        if not group:
            raise NotFoundError(f"Node group '{group_id}' not found")
        _validate(data)
        if "description" in data:
            group.description = data["description"]
        if "environment" in data and data["environment"]:
            group.environment = data["environment"]
        if "parent" in data and data["parent"]:
            group.parent = data["parent"]
        if "is_environment_group" in data:
            group.is_environment_group = bool(data["is_environment_group"])
        if "match_type" in data and data["match_type"]:
            group.match_type = data["match_type"]
        if "rules" in data:
            group.rules = data["rules"] or []
        if "node_ids" in data:
            current = set(group.node_ids)
            wanted = set(data["node_ids"] or [])
            for nid in wanted - current:
                await self._repo.add_node(group_id, nid)
            for nid in current - wanted:
                await self._repo.remove_node(group_id, nid)
            group.node_ids = list(wanted)
        group.updated_at = datetime.utcnow()
        await self._repo.update(group)
        await self._resync(group)
        return group

    async def _resync(self, group: NodeGroup) -> None:
        resolved = await resolve_matching(group, self._node_repo)
        wazuh_ok = puppet_ok = True
        try:
            await self._wazuh.create_agent_group(group.name)
            await self._wazuh.assign_agents_to_group(group.name, resolved["hostnames"])
        except Exception as e:
            wazuh_ok = False
            logger.warning("Wazuh group re-sync failed: %s", e)
        try:
            if group.puppet_group_id:
                await self._puppet.update_node_group(
                    group.puppet_group_id, name=group.name, description=group.description,
                    environment=group.environment, match_type=group.match_type,
                    rules=group.rules, pinned_certnames=resolved["pinned_certnames"],
                )
            else:
                group.puppet_group_id = await self._puppet.create_node_group(
                    group.name, group.description, environment=group.environment,
                    match_type=group.match_type, rules=group.rules,
                    pinned_certnames=resolved["pinned_certnames"],
                ) or None
        except Exception as e:
            puppet_ok = False
            logger.warning("Puppet NC group re-sync failed: %s", e)
        group.wazuh_synced = wazuh_ok
        group.puppet_synced = puppet_ok
        await self._repo.update(group)


class DeleteNodeGroupUseCase:
    def __init__(self, repo, wazuh_client, puppet_client):
        self._repo = repo
        self._wazuh = wazuh_client
        self._puppet = puppet_client

    async def execute(self, group_id: str) -> dict:
        group = await self._repo.find_by_id(group_id)
        if not group:
            raise NotFoundError(f"Node group '{group_id}' not found")
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
    def __init__(self, repo, node_repo=None):
        self._repo = repo
        self._node_repo = node_repo

    async def execute(self) -> list[tuple[NodeGroup, list[str]]]:
        groups = await self._repo.find_all()
        out = []
        for g in groups:
            matching = []
            if self._node_repo:
                matching = (await resolve_matching(g, self._node_repo))["ids"]
            out.append((g, matching))
        return out


class GetNodeGroupUseCase:
    def __init__(self, repo, node_repo=None):
        self._repo = repo
        self._node_repo = node_repo

    async def execute(self, gid: str) -> tuple[NodeGroup, list[str]]:
        g = await self._repo.find_by_id(gid)
        if not g:
            raise NotFoundError(f"Node group '{gid}' not found")
        matching = []
        if self._node_repo:
            matching = (await resolve_matching(g, self._node_repo))["ids"]
        return g, matching


class ListFactsUseCase:
    """Expose available facts and their distinct values for the rule builder."""
    def __init__(self, node_repo):
        self._node_repo = node_repo

    async def execute(self) -> list[dict]:
        nodes = await self._node_repo.find_all({})
        facts = []
        for fact in FACT_ATTRS:
            values = set()
            for n in nodes:
                v = _node_value(n, fact)
                if isinstance(v, (list, tuple)):
                    values.update(str(x) for x in v)
                elif isinstance(v, bool):
                    values.add("true" if v else "false")
                elif v not in (None, ""):
                    values.add(str(v))
            facts.append({"name": fact, "values": sorted(values)[:50]})
        return facts


class PreviewMatchingUseCase:
    """Resolve which registered nodes a candidate rule set would match (live)."""
    def __init__(self, node_repo):
        self._node_repo = node_repo

    async def execute(self, data: dict) -> list[str]:
        _validate(data)
        tmp = NodeGroup(
            id="preview", name="preview",
            match_type=data.get("match_type") or "all",
            rules=data.get("rules") or [],
            node_ids=data.get("node_ids") or [],
        )
        return (await resolve_matching(tmp, self._node_repo))["ids"]


class AddNodeToGroupUseCase:
    def __init__(self, repo, node_repo, wazuh_client=None):
        self._repo = repo
        self._node_repo = node_repo
        self._wazuh = wazuh_client

    async def execute(self, group_id: str, node_id: str) -> dict:
        g = await self._repo.find_by_id(group_id)
        if not g:
            raise NotFoundError(f"Node group '{group_id}' not found")
        n = await self._node_repo.find_by_id(node_id)
        if not n:
            raise NotFoundError(f"Node '{node_id}' not found")
        await self._repo.add_node(group_id, node_id)
        if self._wazuh:
            try:
                await self._wazuh.assign_agents_to_group(g.name, [n.hostname])
            except Exception as e:
                logger.warning("Wazuh assign on pin failed: %s", e)
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
