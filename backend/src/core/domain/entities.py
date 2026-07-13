from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

# The two canonical compliance frameworks supported by the platform.
# CIS Benchmark: the published CIS hardening standard (built-in profile source).
# Internal Referential: BdC/SABC company baseline — distinct entity, derived from
# CIS but independently maintained and may evolve to incorporate other standards.
FRAMEWORKS = [
    {"id": "cis",      "name": "CIS Benchmark"},
    {"id": "internal", "name": "Internal Referential"},
]
FRAMEWORK_IDS = tuple(f["id"] for f in FRAMEWORKS)

# Well-known IDs of the two built-in referential profiles. The CIS Benchmark
# profile is the immutable original; the internal referential is derived from it
# and can be reverted back to it.
CIS_BENCHMARK_PROFILE_ID = "cis-benchmark"
INTERNAL_PROFILE_ID = "sabc-linux-baseline"
# The unified multi-OS referential shipped built-in and seeded from
# platform/seed/referentials/sabc_baseline/. System profile (undeletable).
SABC_BASELINE_PROFILE_ID = "sabc-baseline"


@dataclass
class Node:
    id: str
    hostname: str
    ip: str
    ssh_port: int = 22
    ssh_user: str = "ansible"
    ssh_key_path: str | None = None
    os_family: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    status: str = "registered"
    fqdn: str | None = None
    dns_resolves: bool | None = None
    puppet_enrolled: bool = False
    detection_enrolled: bool = False
    scan_ready: bool = False
    # Tier — the (validation scope × enforcement) combination applied to this
    # node. Defaults to Tier 1 (Level 1, validation only) on enrolment; every
    # reassignment is audited.
    tier_id: str | None = None
    last_seen: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def mark_reachable(self) -> None:
        self.status = "reachable"
        self.last_seen = datetime.utcnow()

    def mark_unreachable(self) -> None:
        self.status = "unreachable"

    def mark_provisioned(self) -> None:
        self.status = "provisioned"

    def is_reachable(self) -> bool:
        return self.status in ("reachable", "provisioned")


@dataclass
class Job:
    id: str
    type: str = "provision"
    status: str = "pending"
    node_id: str | None = None
    target_group: str | None = None
    playbook: str = "site.yml"
    tags: str | None = None
    skip_tags: str | None = None
    extra_vars: dict = field(default_factory=dict)
    logs: list[dict] = field(default_factory=list)
    exit_code: int | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def start(self) -> None:
        self.status = "running"
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def succeed(self, code: int) -> None:
        self.status = "success"
        self.exit_code = code
        self.finished_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def fail(self, code: int) -> None:
        self.status = "failed"
        self.exit_code = code
        self.finished_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def cancel(self) -> None:
        self.status = "cancelled"
        self.finished_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def append_log(self, line: str, level: str = "info") -> None:
        self.logs.append({
            "ts": datetime.utcnow().isoformat(),
            "level": level,
            "line": line,
        })

    def is_terminal(self) -> bool:
        return self.status in ("success", "failed", "cancelled")


@dataclass
class Notification:
    """In-platform notification shown in the header bell — e.g. "enforcement
    finished on web-01" or "post-enforcement scan complete (score 94%)".
    Persisted so operators who weren't watching the job still see the outcome."""
    id: str
    title: str
    message: str | None = None
    kind: str = "info"        # "enforcement" | "scan" | "info"
    severity: str = "info"    # "info" | "success" | "error"
    node_id: str | None = None
    job_id: str | None = None
    is_read: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ComplianceReport:
    id: str
    node_id: str
    source: str
    framework: str
    passed_checks: int
    failed_checks: int
    total_checks: int
    details: list[dict] = field(default_factory=list)
    profile: str | None = None
    duration: float | None = None
    skipped_checks: int = 0
    # ── Scan context (so "which servers scanned against X, at what tier" is a
    #    query). Recorded at scan time; nullable for legacy rows. ──────────────
    compliance_group_id: str | None = None
    profile_id: str | None = None
    profile_version: str | None = None
    tier_id: str | None = None
    tier_name: str | None = None
    os_family: str | None = None          # 'debian' | 'redhat' at scan time
    collected_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def score(self) -> int:
        if self.total_checks == 0:
            return 0
        return round(self.passed_checks / self.total_checks * 100)

    @property
    def severity_counts(self) -> dict:
        """Failed-control counts bucketed by severity, for charting."""
        out = {"high": 0, "medium": 0, "low": 0, "info": 0}
        for d in self.details:
            if d.get("status") == "fail":
                sev = d.get("severity") or "info"
                out[sev] = out.get(sev, 0) + 1
        return out


@dataclass
class ApiKey:
    id: str
    name: str
    key_hash: str
    role: str
    created_at: datetime
    last_used: datetime | None = None
    active: bool = True
    user_id: str | None = None

    ROLES: ClassVar[list[str]] = ["readonly", "operator", "admin"]

    def can_read(self) -> bool:
        return self.active

    def can_operate(self) -> bool:
        return self.active and self.role in ("operator", "admin")

    def can_admin(self) -> bool:
        return self.active and self.role == "admin"


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    role: str = ""  # kept for DB backward compat only, not exposed in API
    email: str | None = None
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: datetime | None = None


@dataclass
class UserGroup:
    id: str
    name: str
    description: str | None = None
    permissions: list[str] = field(default_factory=list)
    is_default: bool = False
    member_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    ALL_PERMISSIONS: ClassVar[list[str]] = [
        "view_nodes", "ping_nodes", "register_nodes", "delete_nodes",
        "run_playbooks", "install_agents",
        "view_compliance", "collect_compliance", "trigger_remediation",
        "cancel_jobs", "view_audit",
        "manage_api_keys", "manage_users", "manage_groups", "manage_node_groups", "change_password",
    ]

    DEFAULT_GROUPS: ClassVar[dict] = {
        "readonly": {
            "description": "Read-only access to all resources",
            "permissions": ["view_nodes", "view_compliance", "view_audit", "change_password"],
        },
        "operator": {
            "description": "Can execute actions on resources",
            "permissions": [
                "view_nodes", "ping_nodes", "register_nodes",
                "run_playbooks", "install_agents",
                "view_compliance", "collect_compliance", "trigger_remediation",
                "cancel_jobs", "view_audit", "change_password",
            ],
        },
        "admin": {
            "description": "Full administrative access",
            "permissions": [
                "view_nodes", "ping_nodes", "register_nodes", "delete_nodes",
                "run_playbooks", "install_agents",
                "view_compliance", "collect_compliance", "trigger_remediation",
                "cancel_jobs", "view_audit",
                "manage_api_keys", "manage_users", "manage_groups", "manage_node_groups", "change_password",
            ],
        },
    }


@dataclass
class AuthPrincipal:
    """Unified auth result from either API key or JWT login."""
    id: str
    name: str
    role: str
    active: bool = True
    source: str = "api_key"  # "api_key" or "jwt"
    permissions: list[str] = field(default_factory=list)

    def can_read(self) -> bool:
        return self.active

    def can_operate(self) -> bool:
        if not self.active:
            return False
        if self.source == "api_key":
            return self.role in ("operator", "admin")
        # JWT: check permission set
        operator_perms = {
            "ping_nodes", "register_nodes", "run_playbooks", "install_agents",
            "collect_compliance", "trigger_remediation", "cancel_jobs",
            "manage_api_keys", "manage_users", "manage_groups", "manage_node_groups",
        }
        return bool(operator_perms & set(self.permissions))

    def can_admin(self) -> bool:
        if not self.active:
            return False
        if self.source == "api_key":
            return self.role == "admin"
        # JWT: check admin permission set
        admin_perms = {"manage_users", "manage_groups", "manage_node_groups"}
        return bool(admin_perms & set(self.permissions))


@dataclass
class NodeGroup:
    id: str
    name: str
    description: str | None = None
    parent: str = "All Nodes"            # parent group name (PE hierarchy)
    environment: str = "production"      # PE environment
    is_environment_group: bool = False   # PE environment-group flag
    match_type: str = "all"              # "all" (AND) | "any" (OR)
    rules: list[dict] = field(default_factory=list)   # [{fact, operator, value}]
    node_ids: list[str] = field(default_factory=list)  # explicitly pinned nodes
    puppet_group_id: str | None = None   # UUID from PE node classifier
    puppet_synced: bool = False
    # "system" = built-in auto-seeded (non-deletable); "user" = admin-created
    group_type: str = "user"
    # InSpec profile to use when scanning members; child groups inherit parent's profile
    inspec_profile_id: str | None = None
    # When true, a detection event for any member node drives the closed
    # remediation loop across this whole group (active response). Off by default.
    active_response_enabled: bool = False
    # OS package repository the group's member nodes pull from. Enforced first by
    # Ansible (works with no Puppet master) and, once a master is up, by Puppet.
    # Shape: {"enabled": bool, "name": str, "url": str, "suite": str,
    #         "components": str, "gpg_key": str}. Empty → use the server default.
    package_repo: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RemediationEvent:
    id: str
    node_id: str
    puppet_job_id: str
    triggered_at: datetime
    # Links back to the config_change_events row that triggered this remediation
    # (formerly wazuh_alert_id — renamed when the detection plane was replaced).
    detection_event_id: str | None = None
    completed_at: datetime | None = None
    outcome: str = "pending"
    resources_fixed: int = 0


@dataclass
class ConfigChangeEvent:
    """One event reported by a node's detection agent.

    Evidence-only: snapshots are stored (hashes + optional content blob) so
    the platform can prove what changed and when — never to roll back.
    ``suppressed`` records the gateway's feedback-storm decision:
    an event stored with suppressed=True did NOT trigger remediation.
    """
    id: str
    node_id: str
    path: str
    event_type: str                       # created|modified|deleted|baseline|heartbeat
    timestamp: datetime                   # agent-side event time
    prev_hash: str | None = None
    new_hash: str | None = None
    file_meta: dict | None = None         # {mode, uid, gid, size, mtime}
    puppet_running: bool = False
    actor: dict | None = None             # {auid, exe, comm} from auditd, or None
    suppressed: bool = False
    suppress_reason: str | None = None    # remediation_pending|puppet_run|baseline|heartbeat
    remediation_event_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Rule:
    id: str
    control_id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    remediation_notes: str | None = None
    active: bool = True
    frameworks: list[dict] = field(default_factory=list)
    code_blocks: dict = field(default_factory=dict)
    scan_blocks: dict = field(default_factory=dict)


# OS families the platform branches on. Everything keys on the FAMILY, never a
# distro name — one implementation per family covers Ubuntu/Debian/Mint (Debian)
# and RHEL/Alma/Rocky/CentOS (RedHat).
OS_FAMILIES = ("debian", "redhat")


def normalize_family(value: str | None) -> str | None:
    """Map a node's os_family fact (or a referential token) to 'debian'|'redhat'.

    Accepts the puppet/facter form ('Debian'/'RedHat'), the InSpec/train form
    ('amazon'), a raw distro id from /etc/os-release ('amzn', 'ol', 'rocky'),
    and the referential form ('debian'/'redhat'). The two families cover every
    derivative the platform supports so scan/enforce resolution never silently
    drops a RHEL-compatible node (Amazon Linux, Oracle Linux, …) to 'Unknown'.
    Returns None for anything genuinely unrecognised."""
    v = (value or "").strip().lower()
    if v in ("debian", "ubuntu", "mint", "raspbian", "kali", "pop", "linuxmint"):
        return "debian"
    if v in ("redhat", "rhel", "centos", "rocky", "almalinux", "alma", "fedora",
             "amazon", "amzn", "oracle", "ol", "oraclelinux", "scientific",
             "cloudlinux"):
        return "redhat"
    return v or None


@dataclass
class ProfileControl:
    """A single control/parameter within a compliance profile (referential).

    Mirrors the unified multi-OS referential columns: the internal SABC
    **Control ID** (the identity, e.g. "JR2.C.1.1.1"), the auto-derived
    **control_key** (its slug), which OS families it **applies_to**, its
    **cis_level** (1|2), the framework provenance reference, and — the core of
    the multi-OS model — per-family Validate/Configure guidance for both the
    Debian and Red Hat families.

    The legacy single ``validate_guideline``/``configure_guideline`` columns are
    retained (mirrored from the Debian family) so existing UI/CSV paths keep
    working while artifact generation and scans consume the per-family columns.
    """
    id: str
    profile_id: str
    section_id: str               # section heading id, e.g. "JR2.C.1.1.0"
    section: str                  # section heading, e.g. "Filesystem Configuration"
    title: str
    position: int = 0
    kind: str = "control"         # "control" | "section" (grouping metadata)
    # ── Unified referential identity + scoping ────────────────────────────────
    control_id: str | None = None         # THE key (internal referential id)
    control_key: str | None = None        # auto-derived slug of control_id
    applies_to: str = "debian;redhat"     # "debian;redhat" | "debian" | "redhat"
    cis_level: int = 1                     # 1 | 2 (blank in source => 1)
    framework_reference: str | None = None  # provenance text only, never parsed
    status: str = "active"                # "active" | "retired" (soft delete)
    # ── Per-family guidance (the multi-OS core) ───────────────────────────────
    validate_debian: str | None = None
    configure_debian: str | None = None
    validate_redhat: str | None = None
    configure_redhat: str | None = None
    # ── Shared / legacy display fields ────────────────────────────────────────
    cis_id: str | None = None
    description: str | None = None
    recommended_value: str | None = None
    agreed_value: str | None = None
    risk_profile: str | None = None       # High / Medium / Low
    rationale: str | None = None
    validate_guideline: str | None = None   # mirror of Debian validate (legacy)
    configure_guideline: str | None = None  # mirror of Debian configure (legacy)
    regulatory: str | None = None
    notes: str | None = None
    check_command: str | None = None
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def families(self) -> list[str]:
        """Families this control applies to, normalised to ('debian','redhat')."""
        out: list[str] = []
        for tok in (self.applies_to or "debian;redhat").replace(",", ";").split(";"):
            fam = normalize_family(tok)
            if fam in OS_FAMILIES and fam not in out:
                out.append(fam)
        return out or ["debian", "redhat"]

    def validate_for(self, family: str) -> str | None:
        return self.validate_redhat if family == "redhat" else self.validate_debian

    def configure_for(self, family: str) -> str | None:
        return self.configure_redhat if family == "redhat" else self.configure_debian


@dataclass
class Profile:
    """A compliance referential — a named collection of controls.

    Two referentials ship as built-in profiles and represent the two distinct
    frameworks declared in ``FRAMEWORKS``:

    * the **CIS Benchmark** (``framework="cis"``) is the pristine published
      standard. It is immutable — read-only for every role, including admins —
      and serves as the canonical "original" that the internal referential can
      be reverted to.
    * the **Internal Referential** (``framework="internal"``) is SABC's own
      baseline, derived from the CIS Benchmark but free to evolve. Admins may
      edit its controls and reset it back to the CIS original.

    User-created profiles have ``framework=None`` and ``source="custom"``.
    """
    id: str
    name: str
    description: str | None = None
    os_family: str = "linux"
    version: str = "1.0.0"
    source: str = "custom"        # "builtin" (seeded) | "custom" (user-created)
    framework: str | None = None  # "cis" | "internal" | None (custom) — see FRAMEWORKS
    # Unified referential ships as a built-in SYSTEM profile: undeletable, but
    # re-seedable (version increments on re-import). Distinct from ``locked``
    # (the CIS original is read-only; the SABC Baseline is editable via import).
    is_system: bool = False
    controls: list[ProfileControl] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_builtin(self) -> bool:
        return self.source == "builtin"

    @property
    def locked(self) -> bool:
        """The CIS Benchmark is the immutable original — no one may edit it."""
        return self.framework == "cis"

    @property
    def control_count(self) -> int:
        return sum(1 for c in self.controls if c.kind == "control")

    @property
    def section_count(self) -> int:
        return len({c.section for c in self.controls})

    def active_controls(self) -> list["ProfileControl"]:
        """Enforceable, non-retired controls (excludes section rows)."""
        return [c for c in self.controls
                if c.kind == "control" and c.status != "retired"]


# ── Tiers — two independent axes: validation scope × enforcement ──────────────
#
# A tier is the combination of two orthogonal decisions:
#   Axis 1 — validation scope : which CIS Levels are scanned
#             (Level 1, or Level 1 + Level 2)  →  ``includes_level_2``
#   Axis 2 — enforcement       : whether drift auto-remediates (Puppet closed
#             loop) or the node is validation-only  →  ``enforce``
#
# The four system tiers are every combination of the two axes:
#
#   ┌────────┬──────────────────────┬───────────────────────┐
#   │ Tier   │ Validation (Axis 1)  │ Enforcement (Axis 2)  │
#   ├────────┼──────────────────────┼───────────────────────┤
#   │ Tier 1 │ Level 1              │ Off (validation only) │
#   │ Tier 2 │ Level 1 + Level 2    │ Off (validation only) │
#   │ Tier 3 │ Level 1              │ On                    │
#   │ Tier 4 │ Level 1 + Level 2    │ On                    │
#   └────────┴──────────────────────┴───────────────────────┘

TIER_1_ID = "tier-1"
TIER_2_ID = "tier-2"
TIER_3_ID = "tier-3"
TIER_4_ID = "tier-4"

# A freshly enrolled node starts on Tier 1 (Level 1, validation only).
DEFAULT_TIER_ID = TIER_1_ID

# Pre-4-tier ids → their equivalent in the two-axis model. Both legacy system
# tiers were validation-only (enforcement used to be a global switch), so they
# map onto the two Off tiers. Applied once at seed time, then removed.
LEGACY_TIER_REMAP = {
    "tier-non-critical": TIER_1_ID,   # Level 1, enforcement off
    "tier-critical": TIER_2_ID,       # Level 1 + 2, enforcement off
}


@dataclass
class Tier:
    """A node tier — the combination of a validation scope (which CIS Levels
    are scanned) and an enforcement decision (whether drift auto-remediates).
    Two control/node properties meet here: the control's CIS Level against the
    tier's ``includes_level_2``, and the tier's ``enforce`` decision against the
    closed remediation loop. System tiers are undeletable; custom tiers (e.g.
    "1.5") add individually-chosen Level-2 controls on top of Level 1."""
    id: str
    name: str
    description: str | None = None
    # Axis 1 — validation scope.
    includes_level_2: bool = False
    # Axis 2 — enforcement: True → drift auto-remediates via the Puppet closed
    # loop; False → the node is scanned/reported but never auto-enforced.
    enforce: bool = False
    is_system: bool = False
    created_by: str | None = None
    # For custom tiers: individually selected Level-2 control_ids added to L1.
    extra_control_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def effective_levels(self) -> set[int]:
        """Levels applied wholesale. Custom extra controls are resolved
        per-control in the scan layer (they may be a subset of Level 2)."""
        return {1, 2} if self.includes_level_2 else {1}


@dataclass
class ComplianceGroup:
    """A platform-only grouping of nodes scanned against a set of profiles.

    Entirely separate from Puppet node groups — these NEVER touch the Puppet NC
    API. A node may belong to several compliance groups (scanned against each
    group's bound profiles)."""
    id: str
    name: str
    description: str | None = None
    profile_ids: list[str] = field(default_factory=list)
    node_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

