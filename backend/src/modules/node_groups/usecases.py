from __future__ import annotations
import logging
import re
import uuid
from datetime import datetime

from core.domain.entities import NodeGroup
from core.errors import NotFoundError, ConflictError, ForbiddenError, ValidationError

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
    """Resolve which registered nodes belong to a group.

    Returns:
        ids              node ids of pinned ∪ rule-matched nodes
        hostnames        their hostnames (for Wazuh agent assignment)
        pinned_certnames certnames of *explicitly pinned* nodes only
        certnames        certnames of *all* matched nodes (pinned ∪ rule)

    ``certnames`` is what we pin into the Puppet classifier rule so every node
    the platform considers a member is explicitly classified into the PE group
    — without relying on PE re-deriving membership from agent facts.
    """
    all_nodes = await node_repo.find_all({})
    pinned_set = set(group.node_ids or [])
    matched_ids, hostnames, pinned_certs, certnames = set(), [], [], []
    for n in all_nodes:
        is_pinned = n.id in pinned_set
        is_rule = node_matches(n, group.rules, group.match_type)
        if is_pinned:
            pinned_certs.append(_certname(n))
        if is_pinned or is_rule:
            matched_ids.add(n.id)
            hostnames.append(n.hostname)
            certnames.append(_certname(n))
    return {"ids": list(matched_ids), "hostnames": hostnames,
            "pinned_certnames": pinned_certs, "certnames": certnames}



def _validate(data: dict) -> None:
    for r in data.get("rules") or []:
        if r.get("fact") not in FACT_ATTRS:
            raise ValidationError(f"Unknown fact '{r.get('fact')}'")
        if r.get("operator") not in VALID_OPERATORS:
            raise ValidationError(f"Invalid operator '{r.get('operator')}'")
    if (data.get("match_type") or "all") not in ("all", "any"):
        raise ValidationError("match_type must be 'all' or 'any'")


# ── Default OS-family hierarchy ───────────────────────────────────────────────
# Built from outermost (SABC Managed) down to version-specific leaves.
# Each node matches all groups for which its facts satisfy the rules.
# Puppet inherits classes top-down; the most specific group wins for InSpec profile.
#
# IMPORTANT — matching against real facts collected by RegisterNodeUseCase._detect_os:
#   os_family  = "Debian" | "RedHat" | "Unknown"   (exact)
#   os_name    = os-release PRETTY_NAME (fallback NAME), e.g. "Ubuntu 22.04.3 LTS",
#                "Debian GNU/Linux 12 (bookworm)", "CentOS Linux 7 (Core)",
#                "Rocky Linux 9.3 (Blue Onyx)", "AlmaLinux 8.9 (Midnight Oncilla)".
#                → distro rules MUST use the "~" (substring/regex) operator, not "=".
#   os_version = os-release VERSION_ID, e.g. "22.04", "12", "7", "8", "9.3".
#                → RHEL-family majors anchor on "^N" (no trailing dot) because
#                  CentOS/Rocky may report bare "8" or "8.9".

_UBUNTU_CHILDREN = [
    {"name": "Ubuntu 20.04", "parent": "Ubuntu", "rules": [
        {"fact": "os_name", "operator": "~", "value": "Ubuntu"},
        {"fact": "os_version", "operator": "~", "value": r"^20\."},
    ]},
    {"name": "Ubuntu 22.04", "parent": "Ubuntu", "rules": [
        {"fact": "os_name", "operator": "~", "value": "Ubuntu"},
        {"fact": "os_version", "operator": "~", "value": r"^22\."},
    ]},
    {"name": "Ubuntu 24.04", "parent": "Ubuntu", "rules": [
        {"fact": "os_name", "operator": "~", "value": "Ubuntu"},
        {"fact": "os_version", "operator": "~", "value": r"^24\."},
    ]},
]

_DEBIAN_CHILDREN = [
    {"name": "Debian 11", "parent": "Debian", "rules": [
        {"fact": "os_name", "operator": "~", "value": "Debian"},
        {"fact": "os_version", "operator": "~", "value": r"^11"},
    ]},
    {"name": "Debian 12", "parent": "Debian", "rules": [
        {"fact": "os_name", "operator": "~", "value": "Debian"},
        {"fact": "os_version", "operator": "~", "value": r"^12"},
    ]},
]

_ROCKY_CHILDREN = [
    {"name": "Rocky Linux 8", "parent": "Rocky Linux", "rules": [
        {"fact": "os_name", "operator": "~", "value": "Rocky"},
        {"fact": "os_version", "operator": "~", "value": r"^8"},
    ]},
    {"name": "Rocky Linux 9", "parent": "Rocky Linux", "rules": [
        {"fact": "os_name", "operator": "~", "value": "Rocky"},
        {"fact": "os_version", "operator": "~", "value": r"^9"},
    ]},
]

_CENTOS_CHILDREN = [
    {"name": "CentOS 7", "parent": "CentOS", "rules": [
        {"fact": "os_name", "operator": "~", "value": "CentOS"},
        {"fact": "os_version", "operator": "~", "value": r"^7"},
    ]},
    {"name": "CentOS Stream 8", "parent": "CentOS", "rules": [
        {"fact": "os_name", "operator": "~", "value": "CentOS"},
        {"fact": "os_version", "operator": "~", "value": r"^8"},
    ]},
]

_ALMA_CHILDREN = [
    {"name": "AlmaLinux 8", "parent": "AlmaLinux", "rules": [
        {"fact": "os_name", "operator": "~", "value": "AlmaLinux"},
        {"fact": "os_version", "operator": "~", "value": r"^8"},
    ]},
    {"name": "AlmaLinux 9", "parent": "AlmaLinux", "rules": [
        {"fact": "os_name", "operator": "~", "value": "AlmaLinux"},
        {"fact": "os_version", "operator": "~", "value": r"^9"},
    ]},
]

# RHEL os-release PRETTY_NAME is "Red Hat Enterprise Linux N.M (...)", so distro
# and version rules match os_name on the "Red Hat Enterprise Linux" substring.
_RHEL_CHILDREN = [
    {"name": "RHEL 7", "parent": "Red Hat Enterprise Linux", "rules": [
        {"fact": "os_name", "operator": "~", "value": "Red Hat Enterprise Linux"},
        {"fact": "os_version", "operator": "~", "value": r"^7"},
    ]},
    {"name": "RHEL 8", "parent": "Red Hat Enterprise Linux", "rules": [
        {"fact": "os_name", "operator": "~", "value": "Red Hat Enterprise Linux"},
        {"fact": "os_version", "operator": "~", "value": r"^8"},
    ]},
    {"name": "RHEL 9", "parent": "Red Hat Enterprise Linux", "rules": [
        {"fact": "os_name", "operator": "~", "value": "Red Hat Enterprise Linux"},
        {"fact": "os_version", "operator": "~", "value": r"^9"},
    ]},
]

DEFAULT_NODE_GROUP_TREE = [
    {
        "name": "SABC Managed Nodes",
        "description": "All nodes enrolled in the SABC compliance platform",
        "parent": "All Nodes",
        "match_type": "any",
        "rules": [
            {"fact": "puppet_enrolled", "operator": "=", "value": "true"},
            {"fact": "wazuh_enrolled", "operator": "=", "value": "true"},
        ],
        "inspec_profile_id": "sabc-linux-baseline",
        "children": [
            {
                "name": "Debian Family",
                "description": "Nodes running a Debian-based OS — uses apt for package management",
                "parent": "SABC Managed Nodes",
                "rules": [{"fact": "os_family", "operator": "=", "value": "Debian"}],
                "inspec_profile_id": "sabc-linux-baseline",
                "children": [
                    {
                        "name": "Ubuntu",
                        "description": "Ubuntu Linux servers",
                        "parent": "Debian Family",
                        "rules": [{"fact": "os_name", "operator": "~", "value": "Ubuntu"}],
                        "inspec_profile_id": "sabc-linux-baseline",
                        "children": _UBUNTU_CHILDREN,
                    },
                    {
                        "name": "Debian",
                        "description": "Debian Linux servers",
                        "parent": "Debian Family",
                        "rules": [{"fact": "os_name", "operator": "~", "value": "Debian"}],
                        "inspec_profile_id": "sabc-linux-baseline",
                        "children": _DEBIAN_CHILDREN,
                    },
                ],
            },
            {
                "name": "RedHat Family",
                "description": "Nodes running a Red Hat-based OS — uses yum/dnf for package management",
                "parent": "SABC Managed Nodes",
                "rules": [{"fact": "os_family", "operator": "=", "value": "RedHat"}],
                "inspec_profile_id": "sabc-linux-baseline",
                "children": [
                    {
                        "name": "Red Hat Enterprise Linux",
                        "description": "Red Hat Enterprise Linux (RHEL) servers",
                        "parent": "RedHat Family",
                        "rules": [{"fact": "os_name", "operator": "~", "value": "Red Hat Enterprise Linux"}],
                        "inspec_profile_id": "sabc-linux-baseline",
                        "children": _RHEL_CHILDREN,
                    },
                    {
                        "name": "Rocky Linux",
                        "description": "Rocky Linux servers",
                        "parent": "RedHat Family",
                        "rules": [{"fact": "os_name", "operator": "~", "value": "Rocky"}],
                        "inspec_profile_id": "sabc-linux-baseline",
                        "children": _ROCKY_CHILDREN,
                    },
                    {
                        "name": "CentOS",
                        "description": "CentOS Linux servers",
                        "parent": "RedHat Family",
                        "rules": [{"fact": "os_name", "operator": "~", "value": "CentOS"}],
                        "inspec_profile_id": "sabc-linux-baseline",
                        "children": _CENTOS_CHILDREN,
                    },
                    {
                        "name": "AlmaLinux",
                        "description": "AlmaLinux servers",
                        "parent": "RedHat Family",
                        "rules": [{"fact": "os_name", "operator": "~", "value": "AlmaLinux"}],
                        "inspec_profile_id": "sabc-linux-baseline",
                        "children": _ALMA_CHILDREN,
                    },
                ],
            },
        ],
    },
]


class SeedDefaultNodeGroupsUseCase:
    """Idempotently seeds the OS-family node group hierarchy at startup.

    Only writes to the local DB — does not call Wazuh or Puppet Enterprise,
    which may not be reachable at startup. System groups appear as unsynced
    and can be pushed to PE once the master host is configured.
    """
    def __init__(self, repo):
        self._repo = repo

    async def execute(self) -> int:
        created = 0
        created += await self._seed_tree(DEFAULT_NODE_GROUP_TREE)
        return created

    async def _seed_tree(self, entries: list[dict]) -> int:
        created = 0
        for entry in entries:
            children = entry.get("children", [])
            existing = await self._repo.find_by_name(entry["name"])
            if not existing:
                now = datetime.utcnow()
                g = NodeGroup(
                    id=str(uuid.uuid4()),
                    name=entry["name"],
                    description=entry.get("description"),
                    parent=entry.get("parent", "All Nodes"),
                    environment="production",
                    is_environment_group=False,
                    match_type=entry.get("match_type", "all"),
                    rules=entry.get("rules", []),
                    node_ids=[],
                    group_type="system",
                    inspec_profile_id=entry.get("inspec_profile_id"),
                    created_at=now,
                    updated_at=now,
                )
                await self._repo.save(g)
                created += 1
                logger.info("Seeded system node group: %s", entry["name"])
            if children:
                created += await self._seed_tree(children)
        return created


class SyncAllNodeGroupsUseCase:
    """Reconcile node groups with Puppet Enterprise and Wazuh.

    Only groups that actually contain nodes are materialised in the Puppet
    console — the auto-seeded OS-family tree would otherwise litter PE with
    empty distro/version groups (e.g. RedHat/CentOS on an all-Ubuntu fleet).
    The reconciliation rule is:

      * A **user** group (admin-created) is always pushed — the admin made it
        on purpose and expects to see it even before nodes match.
      * A **system** group (auto-seeded) is pushed only when its subtree holds
        at least one matching node. "Subtree" is walked by parent pointers, so
        an otherwise-empty ancestor (e.g. "SABC Managed Nodes") is still
        created whenever one of its descendants is populated — the PE hierarchy
        never ends up with a dangling ``parent_id``.
      * A system group that *was* created in PE but is now empty is removed
        from the console (children first) so the view stays clean.

    Every matched node is pinned into the PE rule by certname, so the nodes the
    platform considers members are explicitly classified into the group rather
    than relying on PE re-deriving membership from agent facts.

    Create/update runs parent-first (``created_at`` ascending — the seeder
    inserts parents before children) so a parent's ``puppet_group_id`` exists
    before a child resolves its ``parent_id``. Removal runs child-first
    (reverse order) because PE refuses to delete a group that still has
    children.
    """
    def __init__(self, repo, node_repo, wazuh_client, puppet_client):
        self._repo = repo
        self._node_repo = node_repo
        self._wazuh = wazuh_client
        self._puppet = puppet_client

    async def execute(self) -> dict:
        groups = await self._repo.find_all()  # created_at ascending

        # Is a Puppet master actually configured? If not, the classifier client
        # silently no-ops and we must NOT report groups as synced to PE.
        puppet_ready = False
        try:
            puppet_ready = await self._puppet.is_configured()
        except Exception as e:
            logger.warning("Puppet readiness check failed: %s", e)

        # Resolve membership for every group up front.
        resolved = {g.id: await resolve_matching(g, self._node_repo) for g in groups}
        total_nodes = sum(len(resolved[g.id]["ids"]) for g in groups)

        by_name: dict[str, NodeGroup] = {g.name: g for g in groups}

        # Index children by parent name so we can test whole subtrees.
        children: dict[str, list[NodeGroup]] = {}
        for g in groups:
            children.setdefault(g.parent, []).append(g)

        # A group is "populated" if it — or any descendant — matches a node.
        _pop_cache: dict[str, bool] = {}

        def populated(g: NodeGroup) -> bool:
            if g.id in _pop_cache:
                return _pop_cache[g.id]
            _pop_cache[g.id] = False  # break any pathological parent cycle
            result = bool(resolved[g.id]["ids"]) or any(
                populated(c) for c in children.get(g.name, [])
            )
            _pop_cache[g.id] = result
            return result

        def should_push(g: NodeGroup) -> bool:
            # User groups always appear; a system group is materialised in PE only
            # when it (or a descendant) actually matches a node — so the RedHat
            # branch shows up the moment a RHEL host is recognised, and an
            # all-Ubuntu fleet is not littered with empty CentOS/Rocky groups.
            # Because populated() walks descendants, every ancestor of a matched
            # leaf is itself "populated", so the whole parent chain is created and
            # the PE hierarchy is never left with a dangling parent.
            return g.group_type != "system" or populated(g)

        # Depth within the managed tree (parents have a smaller depth than their
        # children) so we can process parents before children regardless of the
        # created_at order — the PE parent must exist before a child references it.
        def depth(g: NodeGroup) -> int:
            d, seen, cur = 0, set(), g
            while cur and cur.parent in by_name and cur.parent not in seen:
                seen.add(cur.parent)
                cur = by_name[cur.parent]
                d += 1
            return d

        ordered = sorted(groups, key=depth)  # stable → keeps created_at order per level

        # Live map of group name → PE group id, seeded from what is already in PE
        # and updated as we create groups, so a child always resolves the *current*
        # parent id without a stale DB read.
        pe_ids: dict[str, str] = {g.name: g.puppet_group_id for g in groups if g.puppet_group_id}

        def parent_pe_id(g: NodeGroup):
            # None → PE root group. A managed parent resolves to its live PE id.
            if not g.parent or g.parent == "All Nodes" or g.parent not in by_name:
                return None
            return pe_ids.get(g.parent)

        synced = failed = skipped = removed = pushed = 0

        # ── Pass 1: remove now-empty system groups (children before parents) ──
        # Pass 2 owns the skipped count; this pass only deletes stale PE groups.
        for g in reversed(ordered):
            if should_push(g) or g.group_type != "system":
                continue
            if not g.puppet_group_id and not g.wazuh_synced:
                continue
            try:
                if g.puppet_group_id:
                    await self._puppet.delete_node_group(g.puppet_group_id)
            except Exception as e:
                logger.warning("Puppet remove empty group '%s' failed: %s", g.name, e)
            try:
                await self._wazuh.delete_agent_group(g.name)
            except Exception as e:
                logger.warning("Wazuh remove empty group '%s' failed: %s", g.name, e)
            pe_ids.pop(g.name, None)
            g.puppet_group_id = None
            g.puppet_synced = False
            g.wazuh_synced = False
            g.updated_at = datetime.utcnow()
            await self._repo.update(g)
            removed += 1

        # ── Pass 2: create/update populated groups (parents before children) ──
        for g in ordered:
            if not should_push(g):
                skipped += 1
                continue
            certnames = resolved[g.id]["certnames"]
            hostnames = resolved[g.id]["hostnames"]
            wazuh_ok = puppet_ok = True
            try:
                await self._wazuh.create_agent_group(g.name)
                await self._wazuh.assign_agents_to_group(g.name, hostnames)
            except Exception as e:
                wazuh_ok = False
                logger.warning("Wazuh sync failed for '%s': %s", g.name, e)
            try:
                parent_id = parent_pe_id(g)
                if g.puppet_group_id:
                    # Pass parent_id so a group first created flat under the root
                    # is re-parented to its correct place on this sync.
                    await self._puppet.update_node_group(
                        g.puppet_group_id, name=g.name, description=g.description,
                        environment=g.environment, parent_id=parent_id,
                        match_type=g.match_type, rules=g.rules,
                        pinned_certnames=certnames,
                    )
                else:
                    g.puppet_group_id = await self._puppet.create_node_group(
                        g.name, g.description, environment=g.environment,
                        parent_id=parent_id, match_type=g.match_type, rules=g.rules,
                        pinned_certnames=certnames,
                    ) or None
                if g.puppet_group_id:
                    pe_ids[g.name] = g.puppet_group_id
            except Exception as e:
                puppet_ok = False
                logger.warning("Puppet sync failed for '%s': %s", g.name, e)
            # A configured master that produced no group id means the push was a
            # silent no-op — don't let it masquerade as a successful sync.
            if puppet_ready and not g.puppet_group_id:
                puppet_ok = False
            elif g.puppet_group_id:
                pushed += 1
            g.wazuh_synced = wazuh_ok
            g.puppet_synced = puppet_ok
            g.updated_at = datetime.utcnow()
            await self._repo.update(g)
            if wazuh_ok and puppet_ok:
                synced += 1
            else:
                failed += 1

        return {
            "groups_total": len(groups),
            "groups_synced": synced,
            "groups_failed": failed,
            "groups_skipped": skipped,
            "groups_removed": removed,
            "groups_pushed": pushed,
            "nodes_classified": total_nodes,
            "puppet_configured": puppet_ready,
        }


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
            inspec_profile_id=data.get("inspec_profile_id"),
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
                pinned_certnames=resolved["certnames"],
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

    async def _parent_id(self, parent_name: str):
        if not parent_name or parent_name == "All Nodes":
            return None
        parent = await self._repo.find_by_name(parent_name)
        return parent.puppet_group_id if parent else None

    async def _resync(self, group: NodeGroup) -> None:
        resolved = await resolve_matching(group, self._node_repo)
        parent_id = await self._parent_id(group.parent)
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
                    environment=group.environment, parent_id=parent_id,
                    match_type=group.match_type,
                    rules=group.rules, pinned_certnames=resolved["certnames"],
                )
            else:
                group.puppet_group_id = await self._puppet.create_node_group(
                    group.name, group.description, environment=group.environment,
                    parent_id=parent_id, match_type=group.match_type, rules=group.rules,
                    pinned_certnames=resolved["certnames"],
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
        if group.group_type == "system":
            raise ForbiddenError(f"System group '{group.name}' cannot be deleted")
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
