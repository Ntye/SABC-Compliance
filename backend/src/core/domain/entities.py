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
    collected_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def score(self) -> int:
        if self.total_checks == 0:
            return 0
        return round(self.passed_checks / self.total_checks * 100)


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
    role: str
    email: str | None = None
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: datetime | None = None

    ROLES: ClassVar[list[str]] = ["readonly", "operator", "admin"]

    def can_read(self) -> bool:
        return self.active

    def can_operate(self) -> bool:
        return self.active and self.role in ("operator", "admin")

    def can_admin(self) -> bool:
        return self.active and self.role == "admin"


@dataclass
class UserGroup:
    id: str
    name: str
    description: str | None = None
    role: str = "readonly"
    member_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AuthPrincipal:
    """Unified auth result from either API key or JWT login."""
    id: str
    name: str
    role: str
    active: bool = True
    source: str = "api_key"  # "api_key" or "jwt"

    def can_read(self) -> bool:
        return self.active

    def can_operate(self) -> bool:
        return self.active and self.role in ("operator", "admin")

    def can_admin(self) -> bool:
        return self.active and self.role == "admin"


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
