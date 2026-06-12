from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar


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
    inspec_installed: bool = False
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
    inspec_blocks: dict = field(default_factory=dict)
