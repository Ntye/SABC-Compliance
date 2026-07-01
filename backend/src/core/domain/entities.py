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
    wazuh_enrolled: bool = False
    scan_ready: bool = False
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
    environment: str = "production"      # PE environment / shared Wazuh env
    is_environment_group: bool = False   # PE environment-group flag
    match_type: str = "all"              # "all" (AND) | "any" (OR)
    rules: list[dict] = field(default_factory=list)   # [{fact, operator, value}]
    node_ids: list[str] = field(default_factory=list)  # explicitly pinned nodes
    puppet_group_id: str | None = None   # UUID from PE node classifier
    wazuh_synced: bool = False
    puppet_synced: bool = False
    # "system" = built-in auto-seeded (non-deletable); "user" = admin-created
    group_type: str = "user"
    # InSpec profile to use when scanning members; child groups inherit parent's profile
    inspec_profile_id: str | None = None
    # When true, a Wazuh alert for any member node drives the closed remediation
    # loop across this whole group (active response). Off by default.
    active_response_enabled: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RemediationEvent:
    id: str
    node_id: str
    puppet_job_id: str
    triggered_at: datetime
    wazuh_alert_id: str | None = None
    completed_at: datetime | None = None
    outcome: str = "pending"
    resources_fixed: int = 0


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


@dataclass
class ProfileControl:
    """A single control/parameter within a compliance profile (referential).

    Mirrors the SABC "Tech Spec" referential columns: a stable SABC Section ID,
    the CIS mapping, the recommended and (client-specific) agreed values, the
    security rationale and the validate/configure guidelines.
    """
    id: str
    profile_id: str
    section_id: str               # SABC Section ID, e.g. "JR2.C.1.1.0"
    section: str                  # Section heading, e.g. "Filesystem Configuration"
    title: str
    position: int = 0
    kind: str = "control"         # "control" (Type S) | "section" (Type I header)
    cis_id: str | None = None
    description: str | None = None
    recommended_value: str | None = None
    agreed_value: str | None = None
    risk_profile: str | None = None       # High / Medium / Low
    rationale: str | None = None
    validate_guideline: str | None = None
    configure_guideline: str | None = None
    regulatory: str | None = None
    notes: str | None = None
    check_command: str | None = None     # scan check snippet for this control
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


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
    controls: list[ProfileControl] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

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

