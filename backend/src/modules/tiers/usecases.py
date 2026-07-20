"""
Tiers (Section 4) — a node tier is the combination of two independent axes:

    Axis 1 — validation scope : which CIS Levels are scanned
              (Level 1, or Level 1 + Level 2).
    Axis 2 — enforcement       : whether drift auto-remediates via the Puppet
              closed loop, or the node is validation-only.

A control carries a CIS Level (1|2); a node carries exactly one tier. Axis 1
decides which levels apply: level-1 always; level-2 iff the tier includes level
2 OR the control is one of the tier's individually-selected extra controls.
Axis 2 (``tier.enforce``) decides whether a detected change auto-remediates.

The four system tiers (undeletable) are every combination of the two axes:

    Tier 1 — Level 1            · validation only
    Tier 2 — Level 1 + Level 2  · validation only
    Tier 3 — Level 1            · enforcement on
    Tier 4 — Level 1 + Level 2  · enforcement on

Custom tiers (e.g. "1.5") are level-1 plus a hand-picked set of level-2 controls
— each of which MUST be a real control with CIS Level 2 (never invent controls)
— and their own enforcement choice. Custom-tier management is RBAC-gated (admin)
and audited.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from core.domain.entities import (
    DEFAULT_TIER_ID, LEGACY_TIER_REMAP,
    TIER_1_ID, TIER_2_ID, TIER_3_ID, TIER_4_ID, ProfileControl, Tier,
)
from core.domain.interfaces import (
    INodeRepository, IProfileRepository, ITierRepository,
)
from core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


# ── Pure in-scope resolution ──────────────────────────────────────────────────

def control_is_applicable(control: ProfileControl, tier: Tier) -> bool:
    """Whether *control* is in scope for a node in *tier*.

    Level 1 (or blank) is always in scope. Level 2 is in scope when the tier
    includes level 2 wholesale, or when the control is one of the tier's
    individually-selected extra controls.
    """
    level = control.cis_level or 1
    if level <= 1:
        return True
    if tier.includes_level_2:
        return True
    return control.control_id in set(tier.extra_control_ids or [])


def applicable_controls(controls: list[ProfileControl], tier: Tier) -> list[ProfileControl]:
    """The subset of *controls* (enforceable, non-retired) in scope for *tier*."""
    return [
        c for c in controls
        if c.kind == "control" and c.status != "retired" and control_is_applicable(c, tier)
    ]


# ── Seeding ───────────────────────────────────────────────────────────────────

class SeedSystemTiersUseCase:
    """Create the four undeletable system tiers on first boot (idempotent), and
    migrate any node still on a legacy criticality tier onto its two-axis
    equivalent before removing the legacy tier rows."""

    def __init__(self, tier_repo: ITierRepository, node_repo: INodeRepository | None = None) -> None:
        self._repo = tier_repo
        self._nodes = node_repo

    async def execute(self) -> int:
        created = 0
        now = datetime.utcnow()
        # (id, name, includes_level_2, enforce)
        systems = [
            Tier(id=TIER_1_ID, name="Tier 1",
                 description="Level 1 · validation only.",
                 includes_level_2=False, enforce=False, is_system=True, created_at=now),
            Tier(id=TIER_2_ID, name="Tier 2",
                 description="Level 1 + Level 2 · validation only.",
                 includes_level_2=True, enforce=False, is_system=True, created_at=now),
            Tier(id=TIER_3_ID, name="Tier 3",
                 description="Level 1 · enforcement on.",
                 includes_level_2=False, enforce=True, is_system=True, created_at=now),
            Tier(id=TIER_4_ID, name="Tier 4",
                 description="Level 1 + Level 2 · enforcement on.",
                 includes_level_2=True, enforce=True, is_system=True, created_at=now),
        ]
        for t in systems:
            if not await self._repo.find_by_id(t.id):
                await self._repo.save(t)
                created += 1
                logger.info("Seeded system tier: %s", t.name)

        await self._migrate_legacy_tiers()
        return created

    async def _migrate_legacy_tiers(self) -> None:
        """Move nodes off the pre-4-tier criticality tiers and delete those rows.
        Best-effort: a failure here must never block startup."""
        for legacy_id, new_id in LEGACY_TIER_REMAP.items():
            legacy = await self._repo.find_by_id(legacy_id)
            if legacy is None:
                continue
            if self._nodes is not None:
                try:
                    for node in await self._nodes.find_all({}):
                        if node.tier_id == legacy_id:
                            node.tier_id = new_id
                            node.updated_at = datetime.utcnow()
                            await self._nodes.update(node)
                except Exception as exc:
                    logger.error("Legacy tier node remap failed (%s): %s", legacy_id, exc)
                    continue  # leave the legacy row so nodes aren't orphaned
            try:
                await self._repo.delete(legacy_id)
                logger.info("Removed legacy tier '%s' (nodes remapped to %s)", legacy_id, new_id)
            except Exception as exc:
                logger.error("Legacy tier delete failed (%s): %s", legacy_id, exc)


# ── Queries ───────────────────────────────────────────────────────────────────

class ListTiersUseCase:
    def __init__(self, tier_repo: ITierRepository) -> None:
        self._repo = tier_repo

    async def execute(self) -> list[Tier]:
        return await self._repo.find_all()


class GetTierUseCase:
    def __init__(self, tier_repo: ITierRepository) -> None:
        self._repo = tier_repo

    async def execute(self, tier_id: str) -> Tier:
        tier = await self._repo.find_by_id(tier_id)
        if not tier:
            raise NotFoundError(f"Tier '{tier_id}' not found")
        return tier


# ── Custom tier CRUD (admin, audited) ─────────────────────────────────────────

class _TierValidationMixin:
    """Shared validation: extra controls must be real CIS Level-2 controls."""

    _profiles: IProfileRepository

    async def _validate_extra_controls(self, control_ids: list[str]) -> None:
        wanted = [c for c in (control_ids or []) if c]
        if not wanted:
            return
        # Build the set of real Level-2 control_ids across all profiles.
        level2: set[str] = set()
        for p in await self._profiles.find_all():
            for c in p.controls:
                if c.kind == "control" and (c.cis_level or 1) == 2 and c.control_id:
                    level2.add(c.control_id)
        unknown = [c for c in wanted if c not in level2]
        if unknown:
            raise ValidationError(
                "Custom-tier extra controls must be real CIS Level-2 controls. "
                f"Not level-2 (or unknown): {', '.join(sorted(unknown))}"
            )


class CreateTierUseCase(_TierValidationMixin):
    def __init__(self, tier_repo: ITierRepository, profile_repo: IProfileRepository) -> None:
        self._repo = tier_repo
        self._profiles = profile_repo

    async def execute(self, data: dict, created_by: str | None = None) -> Tier:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("Tier name is required.")
        if await self._repo.find_by_name(name):
            raise ConflictError(f"A tier named '{name}' already exists.")
        includes_l2 = bool(data.get("includes_level_2"))
        enforce = bool(data.get("enforce"))
        extra = list(data.get("extra_control_ids") or [])
        # A custom tier that already includes all of level 2 needs no extra list.
        if includes_l2 and extra:
            extra = []
        await self._validate_extra_controls(extra)
        tier = Tier(
            id=str(uuid.uuid4()),
            name=name,
            description=(data.get("description") or None),
            includes_level_2=includes_l2,
            enforce=enforce,
            is_system=False,
            created_by=created_by,
            extra_control_ids=extra,
            created_at=datetime.utcnow(),
        )
        await self._repo.save(tier)
        logger.info("Created custom tier '%s' (by=%s, +L2=%s, enforce=%s, extras=%d)",
                    name, created_by, includes_l2, enforce, len(extra))
        return tier


class UpdateTierUseCase(_TierValidationMixin):
    def __init__(self, tier_repo: ITierRepository, profile_repo: IProfileRepository) -> None:
        self._repo = tier_repo
        self._profiles = profile_repo

    async def execute(self, tier_id: str, data: dict) -> Tier:
        tier = await self._repo.find_by_id(tier_id)
        if not tier:
            raise NotFoundError(f"Tier '{tier_id}' not found")
        if tier.is_system:
            raise ForbiddenError("System tiers cannot be modified.")
        if "name" in data and data["name"]:
            name = str(data["name"]).strip()
            clash = await self._repo.find_by_name(name)
            if clash and clash.id != tier_id:
                raise ConflictError(f"A tier named '{name}' already exists.")
            tier.name = name
        if "description" in data:
            tier.description = data["description"] or None
        if "includes_level_2" in data:
            tier.includes_level_2 = bool(data["includes_level_2"])
        if "enforce" in data:
            tier.enforce = bool(data["enforce"])
        if "extra_control_ids" in data:
            extra = list(data["extra_control_ids"] or [])
            if tier.includes_level_2:
                extra = []
            await self._validate_extra_controls(extra)
            tier.extra_control_ids = extra
        await self._repo.update(tier)
        return await self._repo.find_by_id(tier_id)


class DeleteTierUseCase:
    def __init__(self, tier_repo: ITierRepository, node_repo: INodeRepository) -> None:
        self._repo = tier_repo
        self._nodes = node_repo

    async def execute(self, tier_id: str) -> dict:
        tier = await self._repo.find_by_id(tier_id)
        if not tier:
            raise NotFoundError(f"Tier '{tier_id}' not found")
        if tier.is_system:
            raise ForbiddenError("System tiers cannot be deleted.")
        # Re-home any node on this tier back to the default tier so nothing is orphaned.
        moved = 0
        for node in await self._nodes.find_all({}):
            if node.tier_id == tier_id:
                node.tier_id = DEFAULT_TIER_ID
                node.updated_at = datetime.utcnow()
                await self._nodes.update(node)
                moved += 1
        await self._repo.delete(tier_id)
        logger.info("Deleted tier '%s'; re-homed %d node(s) to the default tier", tier.name, moved)
        return {"message": f"Tier '{tier.name}' deleted", "nodes_rehomed": moved}


class AssignNodeTierUseCase:
    """Assign a node to a tier. Audited via the HTTP audit middleware plus an
    explicit log line recording old→new tier and the acting principal."""

    def __init__(self, node_repo: INodeRepository, tier_repo: ITierRepository) -> None:
        self._nodes = node_repo
        self._tiers = tier_repo

    async def execute(self, node_id: str, tier_id: str, actor: str | None = None) -> dict:
        node = await self._nodes.find_by_id(node_id)
        if not node:
            node = await self._nodes.find_by_hostname(node_id)
        if not node:
            raise NotFoundError(f"Node '{node_id}' not found")
        tier = await self._tiers.find_by_id(tier_id)
        if not tier:
            raise NotFoundError(f"Tier '{tier_id}' not found")
        old = node.tier_id
        node.tier_id = tier.id
        node.updated_at = datetime.utcnow()
        await self._nodes.update(node)
        logger.info("AUDIT tier-assign: node=%s (%s) tier %s -> %s by=%s",
                    node.hostname, node.id, old, tier.id, actor or "unknown")
        return {"node_id": node.id, "hostname": node.hostname,
                "old_tier_id": old, "tier_id": tier.id, "tier_name": tier.name}


class AssignGroupTierUseCase:
    """Assign every member of a Puppet node group to a tier in one action.

    Tier is a per-node attribute, so a group assignment simply stamps the tier on
    each member. Audited per node via the same log line as single-node assigns.
    """

    def __init__(self, node_group_repo, node_repo: INodeRepository,
                 tier_repo: ITierRepository) -> None:
        self._groups = node_group_repo
        self._nodes = node_repo
        self._tiers = tier_repo

    async def execute(self, group_id: str, tier_id: str, actor: str | None = None) -> dict:
        group = await self._groups.find_by_id(group_id)
        if not group:
            raise NotFoundError(f"Node group '{group_id}' not found")
        tier = await self._tiers.find_by_id(tier_id)
        if not tier:
            raise NotFoundError(f"Tier '{tier_id}' not found")

        assigned = 0
        for nid in group.node_ids or []:
            node = await self._nodes.find_by_id(nid)
            if node is None:
                continue
            old = node.tier_id
            node.tier_id = tier.id
            node.updated_at = datetime.utcnow()
            await self._nodes.update(node)
            assigned += 1
            logger.info("AUDIT tier-assign(group=%s): node=%s tier %s -> %s by=%s",
                        group.name, node.hostname, old, tier.id, actor or "unknown")
        return {"group_id": group.id, "group_name": group.name,
                "tier_id": tier.id, "tier_name": tier.name,
                "members": len(group.node_ids or []), "assigned": assigned}


async def resolve_node_tier(node, tier_repo: ITierRepository) -> Tier:
    """The node's tier, defaulting to Tier 1 when unset/missing."""
    tid = getattr(node, "tier_id", None) or DEFAULT_TIER_ID
    tier = await tier_repo.find_by_id(tid)
    if tier is None:
        tier = await tier_repo.find_by_id(DEFAULT_TIER_ID)
    return tier
