"""
Scan resolution (Section 6).

The unit of scanning is the **compliance group** → its bound **profiles** → its
**member nodes**. For each member node, each bound profile is scanned, but only
the controls the node's **tier** makes applicable, in the node's **OS family**.

This module resolves that plan without running anything, so it is pure and
testable:

    compliance groups (of a node)  →  bound profiles
                                   →  tier-applicable controls
                                   →  family-relevant controls (node os.family)

A node in NO compliance group still resolves against the built-in SABC Baseline
(fallback) so a freshly-enrolled node scans out of the box — supporting the
acceptance scenario (enrol → tier → full cycle, no imports needed).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from core.domain.entities import (
    OS_FAMILIES, SABC_BASELINE_PROFILE_ID, Node, Profile, Tier, normalize_family,
)
from core.domain.interfaces import (
    IComplianceGroupRepository, INodeRepository, IProfileRepository, ITierRepository,
)
from modules.tiers.usecases import applicable_controls, resolve_node_tier

logger = logging.getLogger(__name__)


def _plan_family(os_family: Optional[str]) -> Optional[str]:
    """The family used to narrow a node's scan plan: 'debian' | 'redhat' | None.

    A node whose enrolment-time OS detection failed carries os_family='Unknown'
    (or an unrecognised token). ``normalize_family`` passes such tokens through
    verbatim, and filtering controls with ``'unknown' in c.families()`` matches
    NOTHING — the node resolves an empty plan and every scan 422s. Since all
    generated artifacts self-guard by family at runtime (InSpec ``os.debian?`` /
    ``os.redhat?``, Puppet ``$facts['os']['family']``), the safe behaviour is to
    keep every control in the plan (family=None) and let the runtime guards on
    the node decide which branch applies."""
    fam = normalize_family(os_family)
    return fam if fam in OS_FAMILIES else None


def numeric_key(control_id: Optional[str]) -> str:
    """Numeric hierarchy key of a referential id, with a trailing section zero
    dropped: ``JR2.C.1.1.0`` → ``1.1``; ``JR2.C.1.1.1.4`` → ``1.1.1.4``;
    ``JR2.C.1.0`` → ``1``. Non-numeric segments (``JR2``, ``C``) are ignored."""
    parts = [p for p in (control_id or "").split(".") if p.isdigit()]
    while len(parts) > 1 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)


@dataclass
class ProfileScanSpec:
    """One profile to scan a node against, already narrowed to the tier- and
    family-applicable controls."""
    profile_id: str
    profile_name: str
    profile_version: str
    compliance_group_id: Optional[str]
    compliance_group_name: Optional[str]
    applicable_control_ids: list[str]
    inspec_dir: Optional[str] = None
    # numeric section key ("1", "1.1", "1.1.1") → section heading title, built
    # from the profile's section rows so scan results can be grouped under the
    # referential's own named sections instead of a generic "Other" bucket.
    section_titles: dict[str, str] = field(default_factory=dict)

    @property
    def control_count(self) -> int:
        return len(self.applicable_control_ids)


@dataclass
class NodeScanPlan:
    node_id: str
    hostname: str
    os_family: Optional[str]              # 'debian' | 'redhat' | None
    tier_id: str
    tier_name: str
    specs: list[ProfileScanSpec] = field(default_factory=list)

    @property
    def total_controls(self) -> int:
        return sum(s.control_count for s in self.specs)


class ScanPlanResolver:
    """Resolves group → profiles → tier → family scan plans for nodes."""

    def __init__(
        self,
        node_repo: INodeRepository,
        group_repo: IComplianceGroupRepository,
        tier_repo: ITierRepository,
        profile_repo: IProfileRepository,
        inspec_dir_for: Optional[Callable[[Profile], Optional[str]]] = None,
    ) -> None:
        self._nodes = node_repo
        self._groups = group_repo
        self._tiers = tier_repo
        self._profiles = profile_repo
        self._inspec_dir_for = inspec_dir_for or (lambda p: None)

    # ── Per-node ──────────────────────────────────────────────────────────────

    async def for_node(self, node: Node) -> NodeScanPlan:
        """Resolve the scan plan for a single node via its group memberships.

        Applicable profiles come from EVERY compliance group the node belongs to
        (a node may be in several). A node in no group falls back to the built-in
        SABC Baseline so it still scans.
        """
        tier = await resolve_node_tier(node, self._tiers)
        family = _plan_family(node.os_family)

        groups = await self._groups.find_for_node(node.id)
        # profile_id → group provenance (first group that binds it).
        profile_groups: dict[str, tuple[str, str]] = {}
        for g in groups:
            for pid in g.profile_ids:
                profile_groups.setdefault(pid, (g.id, g.name))

        if not profile_groups:
            # Fallback: built-in baseline, no group provenance.
            profile_groups = {SABC_BASELINE_PROFILE_ID: (None, None)}

        plan = NodeScanPlan(
            node_id=node.id, hostname=node.hostname, os_family=family,
            tier_id=tier.id, tier_name=tier.name,
        )
        for pid, (gid, gname) in profile_groups.items():
            spec = await self._spec(pid, tier, family, gid, gname)
            if spec is not None:
                plan.specs.append(spec)
        return plan

    async def _spec(self, profile_id: str, tier: Tier, family: Optional[str],
                    group_id: Optional[str], group_name: Optional[str]
                    ) -> Optional[ProfileScanSpec]:
        profile = await self._profiles.find_by_id(profile_id)
        if profile is None:
            logger.warning("Scan plan: bound profile '%s' no longer exists", profile_id)
            return None
        # Tier decides levels; family decides which controls run on this node.
        tier_ok = applicable_controls(profile.controls, tier)
        applicable = [
            c.control_id
            for c in tier_ok
            if c.control_id and (family is None or family in c.families())
        ]
        # Section headings (kind="section") name each level of the hierarchy, so
        # the scan can label "1.1" with "Filesystem Configuration" and group
        # under the referential's own top sections rather than "Other".
        section_titles: dict[str, str] = {}
        for c in profile.controls:
            if c.kind == "section":
                key = numeric_key(c.control_id or c.section_id)
                title = (c.title or c.section or "").strip()
                if key and title:
                    section_titles[key] = title
        return ProfileScanSpec(
            profile_id=profile.id,
            profile_name=profile.name,
            profile_version=profile.version,
            compliance_group_id=group_id,
            compliance_group_name=group_name,
            applicable_control_ids=applicable,
            inspec_dir=self._inspec_dir_for(profile),
            section_titles=section_titles,
        )

    # ── Per-group ─────────────────────────────────────────────────────────────

    async def for_group(self, group) -> list[NodeScanPlan]:
        """Resolve a plan for every member node of *group*, scanning each member
        against the group's bound profiles (tier- and family-narrowed)."""
        plans: list[NodeScanPlan] = []
        for node_id in group.node_ids:
            node = await self._nodes.find_by_id(node_id)
            if node is None:
                continue
            tier = await resolve_node_tier(node, self._tiers)
            family = _plan_family(node.os_family)
            plan = NodeScanPlan(
                node_id=node.id, hostname=node.hostname, os_family=family,
                tier_id=tier.id, tier_name=tier.name,
            )
            for pid in group.profile_ids:
                spec = await self._spec(pid, tier, family, group.id, group.name)
                if spec is not None:
                    plan.specs.append(spec)
            plans.append(plan)
        return plans
