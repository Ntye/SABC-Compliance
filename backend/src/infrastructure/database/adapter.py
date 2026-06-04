from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import (
    Column, Integer, MetaData, String, Table, Text, select, delete, update, func, text
)
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from core.domain.entities import (
    ApiKey, ComplianceReport, Job, Node, RemediationEvent, Rule, User,
)
from core.domain.interfaces import (
    IApiKeyRepository, IAuditRepository, IComplianceRepository,
    IJobRepository, INodeRepository, IPlatformConfigRepository,
    IRuleRepository, IUserRepository,
)

logger = logging.getLogger(__name__)

metadata = MetaData()

nodes_table = Table(
    "nodes", metadata,
    Column("id", Text, primary_key=True),
    Column("hostname", Text, nullable=False, unique=True),
    Column("ip", Text, nullable=False),
    Column("ssh_port", Integer, default=22),
    Column("ssh_user", Text, default="ansible"),
    Column("ssh_key_path", Text),
    Column("os_family", Text),
    Column("os_name", Text),
    Column("os_version", Text),
    Column("fqdn", Text),
    Column("dns_resolves", Integer),
    Column("description", Text),
    Column("tags", Text, default="[]"),
    Column("status", Text, default="registered"),
    Column("puppet_enrolled", Integer, default=0),
    Column("wazuh_enrolled", Integer, default=0),
    Column("inspec_installed", Integer, default=0),
    Column("last_seen", Text),
    Column("created_at", Text),
    Column("updated_at", Text),
)

jobs_table = Table(
    "jobs", metadata,
    Column("id", Text, primary_key=True),
    Column("type", Text, default="provision"),
    Column("status", Text, default="pending"),
    Column("node_id", Text),
    Column("target_group", Text),
    Column("playbook", Text, default="site.yml"),
    Column("tags", Text),
    Column("skip_tags", Text),
    Column("extra_vars", Text, default="{}"),
    Column("exit_code", Integer),
    Column("created_at", Text),
    Column("updated_at", Text),
    Column("started_at", Text),
    Column("finished_at", Text),
)

# Each log line is its own row — avoids the read-modify-write race condition
# that would occur if logs were stored as a JSON array in the jobs table.
job_logs_table = Table(
    "job_logs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("job_id", Text, nullable=False),
    Column("ts", Text),
    Column("level", Text, default="info"),
    Column("line", Text),
)

compliance_reports_table = Table(
    "compliance_reports", metadata,
    Column("id", Text, primary_key=True),
    Column("node_id", Text, nullable=False),
    Column("source", Text),
    Column("framework", Text),
    Column("passed_checks", Integer, default=0),
    Column("failed_checks", Integer, default=0),
    Column("total_checks", Integer, default=0),
    Column("score", Integer, default=0),
    Column("details", Text, default="[]"),
    Column("collected_at", Text),
)

remediation_events_table = Table(
    "remediation_events", metadata,
    Column("id", Text, primary_key=True),
    Column("node_id", Text, nullable=False),
    Column("wazuh_alert_id", Text),
    Column("puppet_job_id", Text),
    Column("triggered_at", Text),
    Column("completed_at", Text),
    Column("outcome", Text, default="pending"),
    Column("resources_fixed", Integer, default=0),
)

api_keys_table = Table(
    "api_keys", metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("key_hash", Text, nullable=False, unique=True),
    Column("role", Text, default="readonly"),
    Column("created_at", Text),
    Column("last_used", Text),
    Column("active", Integer, default=1),
    Column("user_id", Text),
)

users_table = Table(
    "users", metadata,
    Column("id", Text, primary_key=True),
    Column("username", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("role", Text, default="readonly"),
    Column("email", Text),
    Column("active", Integer, default=1),
    Column("created_at", Text),
    Column("last_login", Text),
)

audit_log_table = Table(
    "audit_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ts", Text),
    Column("method", Text),
    Column("path", Text),
    Column("status_code", Integer),
    Column("ip", Text),
    Column("user_agent", Text),
    Column("duration_ms", Integer),
    Column("api_key_name", Text),
)

platform_config_table = Table(
    "platform_config", metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text),
    Column("updated_at", Text),
)

rules_table = Table(
    "rules", metadata,
    Column("id", Text, primary_key=True),
    Column("control_id", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("remediation_notes", Text),
    Column("active", Integer, default=1),
    Column("frameworks", Text, default="[]"),
    Column("code_blocks", Text, default="{}"),
    Column("inspec_blocks", Text, default="{}"),
    Column("created_at", Text),
    Column("updated_at", Text),
)


def _dt(val: str | None) -> datetime | None:
    if val is None:
        return None
    return datetime.fromisoformat(val)


def _ts(val: datetime | None) -> str | None:
    if val is None:
        return None
    return val.isoformat()


async def create_db(db_path: str) -> tuple[AsyncEngine, async_sessionmaker]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        # Idempotent column migrations for older DB schemas
        for col, typ in [("fqdn", "TEXT"), ("dns_resolves", "INTEGER")]:
            try:
                await conn.execute(text(f"ALTER TABLE nodes ADD COLUMN {col} {typ}"))
            except Exception:
                pass  # column already exists
        try:
            await conn.execute(text("ALTER TABLE api_keys ADD COLUMN user_id TEXT"))
        except Exception:
            pass  # column already exists
        # jobs.logs was a JSON blob that suffered a write-race; now replaced by
        # the job_logs table.  Drop the old column if it exists (SQLite workaround:
        # we just leave it — SQLite ignored unused columns and doesn't support
        # DROP COLUMN before 3.35, so we simply stop writing/reading it).

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


# ── Node Repository ──────────────────────────────────────────────────────────

class NodeRepository(INodeRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    def _to_entity(self, row) -> Node:
        return Node(
            id=row.id,
            hostname=row.hostname,
            ip=row.ip,
            ssh_port=row.ssh_port or 22,
            ssh_user=row.ssh_user or "ansible",
            ssh_key_path=row.ssh_key_path,
            os_family=row.os_family,
            os_name=row.os_name,
            os_version=row.os_version,
            fqdn=getattr(row, 'fqdn', None),
            dns_resolves=None if getattr(row, 'dns_resolves', None) is None else bool(row.dns_resolves),
            description=row.description,
            tags=json.loads(row.tags or "[]"),
            status=row.status or "registered",
            puppet_enrolled=bool(row.puppet_enrolled),
            wazuh_enrolled=bool(row.wazuh_enrolled),
            inspec_installed=bool(row.inspec_installed),
            last_seen=_dt(row.last_seen),
            created_at=_dt(row.created_at) or datetime.utcnow(),
            updated_at=_dt(row.updated_at) or datetime.utcnow(),
        )

    def _to_dict(self, node: Node) -> dict:
        return {
            "id": node.id,
            "hostname": node.hostname,
            "ip": node.ip,
            "ssh_port": node.ssh_port,
            "ssh_user": node.ssh_user,
            "ssh_key_path": node.ssh_key_path,
            "os_family": node.os_family,
            "os_name": node.os_name,
            "os_version": node.os_version,
            "fqdn": node.fqdn,
            "dns_resolves": None if node.dns_resolves is None else int(node.dns_resolves),
            "description": node.description,
            "tags": json.dumps(node.tags),
            "status": node.status,
            "puppet_enrolled": int(node.puppet_enrolled),
            "wazuh_enrolled": int(node.wazuh_enrolled),
            "inspec_installed": int(node.inspec_installed),
            "last_seen": _ts(node.last_seen),
            "created_at": _ts(node.created_at),
            "updated_at": _ts(node.updated_at),
        }

    async def save(self, node: Node) -> None:
        async with self._session() as s:
            await s.execute(nodes_table.insert().values(**self._to_dict(node)))
            await s.commit()

    async def find_by_id(self, id: str) -> Node | None:
        async with self._session() as s:
            row = (await s.execute(select(nodes_table).where(nodes_table.c.id == id))).first()
            return self._to_entity(row) if row else None

    async def find_by_hostname(self, hostname: str) -> Node | None:
        async with self._session() as s:
            row = (await s.execute(select(nodes_table).where(nodes_table.c.hostname == hostname))).first()
            return self._to_entity(row) if row else None

    async def find_all(self, filters: dict) -> list[Node]:
        async with self._session() as s:
            q = select(nodes_table)
            if filters.get("status"):
                q = q.where(nodes_table.c.status == filters["status"])
            if filters.get("os_family"):
                q = q.where(nodes_table.c.os_family == filters["os_family"])
            rows = (await s.execute(q)).all()
            return [self._to_entity(r) for r in rows]

    async def update(self, node: Node) -> None:
        async with self._session() as s:
            await s.execute(
                update(nodes_table).where(nodes_table.c.id == node.id).values(**self._to_dict(node))
            )
            await s.commit()

    async def delete(self, id: str) -> None:
        async with self._session() as s:
            await s.execute(delete(nodes_table).where(nodes_table.c.id == id))
            await s.commit()


# ── Job Repository ────────────────────────────────────────────────────────────

class JobRepository(IJobRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    def _to_entity(self, row, logs: list | None = None) -> Job:
        return Job(
            id=row.id,
            type=row.type or "provision",
            status=row.status or "pending",
            node_id=row.node_id,
            target_group=row.target_group,
            playbook=row.playbook or "site.yml",
            tags=row.tags,
            skip_tags=row.skip_tags,
            extra_vars=json.loads(row.extra_vars or "{}"),
            logs=logs if logs is not None else [],
            exit_code=row.exit_code,
            created_at=_dt(row.created_at) or datetime.utcnow(),
            updated_at=_dt(row.updated_at) or datetime.utcnow(),
            started_at=_dt(row.started_at),
            finished_at=_dt(row.finished_at),
        )

    def _to_dict(self, job: Job) -> dict:
        return {
            "id": job.id,
            "type": job.type,
            "status": job.status,
            "node_id": job.node_id,
            "target_group": job.target_group,
            "playbook": job.playbook,
            "tags": job.tags,
            "skip_tags": job.skip_tags,
            "extra_vars": json.dumps(job.extra_vars),
            "exit_code": job.exit_code,
            "created_at": _ts(job.created_at),
            "updated_at": _ts(job.updated_at),
            "started_at": _ts(job.started_at),
            "finished_at": _ts(job.finished_at),
        }

    async def save(self, job: Job) -> None:
        async with self._session() as s:
            await s.execute(jobs_table.insert().values(**self._to_dict(job)))
            await s.commit()

    async def find_by_id(self, id: str) -> Job | None:
        async with self._session() as s:
            row = (await s.execute(select(jobs_table).where(jobs_table.c.id == id))).first()
            if not row:
                return None
            log_rows = (await s.execute(
                select(job_logs_table)
                .where(job_logs_table.c.job_id == id)
                .order_by(job_logs_table.c.id)
            )).all()
            logs = [{"ts": r.ts, "level": r.level, "line": r.line} for r in log_rows]
            return self._to_entity(row, logs)

    async def find_all(self, limit: int) -> list[Job]:
        async with self._session() as s:
            q = select(jobs_table).order_by(jobs_table.c.created_at.desc()).limit(limit)
            rows = (await s.execute(q)).all()
            return [self._to_entity(r) for r in rows]

    async def update(self, job: Job) -> None:
        async with self._session() as s:
            await s.execute(
                update(jobs_table).where(jobs_table.c.id == job.id).values(**self._to_dict(job))
            )
            await s.commit()

    async def append_log(self, job_id: str, entry: dict) -> None:
        async with self._session() as s:
            await s.execute(job_logs_table.insert().values(
                job_id=job_id,
                ts=entry.get("ts"),
                level=entry.get("level", "info"),
                line=entry.get("line", ""),
            ))
            await s.commit()


# ── Compliance Repository ─────────────────────────────────────────────────────

class ComplianceRepository(IComplianceRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    def _report_to_entity(self, row) -> ComplianceReport:
        return ComplianceReport(
            id=row.id,
            node_id=row.node_id,
            source=row.source or "puppet",
            framework=row.framework or "cis",
            passed_checks=row.passed_checks or 0,
            failed_checks=row.failed_checks or 0,
            total_checks=row.total_checks or 0,
            details=json.loads(row.details or "[]"),
            collected_at=_dt(row.collected_at) or datetime.utcnow(),
        )

    def _remediation_to_entity(self, row) -> RemediationEvent:
        return RemediationEvent(
            id=row.id,
            node_id=row.node_id,
            wazuh_alert_id=row.wazuh_alert_id,
            puppet_job_id=row.puppet_job_id or "",
            triggered_at=_dt(row.triggered_at) or datetime.utcnow(),
            completed_at=_dt(row.completed_at),
            outcome=row.outcome or "pending",
            resources_fixed=row.resources_fixed or 0,
        )

    async def save_report(self, report: ComplianceReport) -> None:
        async with self._session() as s:
            await s.execute(compliance_reports_table.insert().values(
                id=report.id, node_id=report.node_id, source=report.source,
                framework=report.framework, passed_checks=report.passed_checks,
                failed_checks=report.failed_checks, total_checks=report.total_checks,
                score=report.score, details=json.dumps(report.details),
                collected_at=_ts(report.collected_at),
            ))
            await s.commit()

    async def find_by_node(self, node_id: str) -> list[ComplianceReport]:
        async with self._session() as s:
            rows = (await s.execute(
                select(compliance_reports_table)
                .where(compliance_reports_table.c.node_id == node_id)
                .order_by(compliance_reports_table.c.collected_at.desc())
                .limit(10)
            )).all()
            return [self._report_to_entity(r) for r in rows]

    async def find_summary(self) -> list[dict]:
        async with self._session() as s:
            node_rows = (await s.execute(select(nodes_table))).all()
            results = []
            for node_row in node_rows:
                reports_task = s.execute(
                    select(compliance_reports_table)
                    .where(compliance_reports_table.c.node_id == node_row.id)
                    .order_by(compliance_reports_table.c.collected_at.desc())
                    .limit(10)
                )
                remediations_task = s.execute(
                    select(remediation_events_table)
                    .where(remediation_events_table.c.node_id == node_row.id)
                    .order_by(remediation_events_table.c.triggered_at.desc())
                    .limit(5)
                )
                reports_result, remediations_result = await asyncio.gather(reports_task, remediations_task)
                reports = [self._report_to_entity(r) for r in reports_result.all()]
                remediations = [self._remediation_to_entity(r) for r in remediations_result.all()]

                node = NodeRepository(self._session)._to_entity(node_row)
                results.append({
                    "node_id": node.id,
                    "hostname": node.hostname,
                    "ip": node.ip,
                    "os_family": node.os_family,
                    "status": node.status,
                    "puppet_enrolled": node.puppet_enrolled,
                    "wazuh_enrolled": node.wazuh_enrolled,
                    "inspec_installed": node.inspec_installed,
                    "reports": [
                        {
                            "id": r.id, "source": r.source, "framework": r.framework,
                            "score": r.score, "passed_checks": r.passed_checks,
                            "failed_checks": r.failed_checks, "total_checks": r.total_checks,
                            "collected_at": r.collected_at.isoformat(),
                        }
                        for r in reports
                    ],
                    "remediations": [
                        {
                            "id": r.id, "outcome": r.outcome,
                            "resources_fixed": r.resources_fixed,
                            "triggered_at": r.triggered_at.isoformat(),
                            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                            "wazuh_alert_id": r.wazuh_alert_id,
                            "puppet_job_id": r.puppet_job_id,
                        }
                        for r in remediations
                    ],
                })
            return results

    async def save_remediation(self, event: RemediationEvent) -> None:
        async with self._session() as s:
            await s.execute(remediation_events_table.insert().values(
                id=event.id, node_id=event.node_id, wazuh_alert_id=event.wazuh_alert_id,
                puppet_job_id=event.puppet_job_id, triggered_at=_ts(event.triggered_at),
                completed_at=_ts(event.completed_at), outcome=event.outcome,
                resources_fixed=event.resources_fixed,
            ))
            await s.commit()

    async def find_remediations(self, node_id: str) -> list[RemediationEvent]:
        async with self._session() as s:
            rows = (await s.execute(
                select(remediation_events_table)
                .where(remediation_events_table.c.node_id == node_id)
                .order_by(remediation_events_table.c.triggered_at.desc())
            )).all()
            return [self._remediation_to_entity(r) for r in rows]

    async def find_all_remediations(self, limit: int) -> list[RemediationEvent]:
        async with self._session() as s:
            rows = (await s.execute(
                select(remediation_events_table)
                .order_by(remediation_events_table.c.triggered_at.desc())
                .limit(limit)
            )).all()
            return [self._remediation_to_entity(r) for r in rows]

    async def find_remediation(self, id: str) -> RemediationEvent | None:
        async with self._session() as s:
            row = (await s.execute(
                select(remediation_events_table).where(remediation_events_table.c.id == id)
            )).first()
            return self._remediation_to_entity(row) if row else None

    async def update_remediation(self, event: RemediationEvent) -> None:
        async with self._session() as s:
            await s.execute(
                update(remediation_events_table)
                .where(remediation_events_table.c.id == event.id)
                .values(
                    outcome=event.outcome,
                    completed_at=_ts(event.completed_at),
                    resources_fixed=event.resources_fixed,
                )
            )
            await s.commit()


# ── ApiKey Repository ─────────────────────────────────────────────────────────

class ApiKeyRepository(IApiKeyRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    def _to_entity(self, row) -> ApiKey:
        return ApiKey(
            id=row.id,
            name=row.name,
            key_hash=row.key_hash,
            role=row.role or "readonly",
            created_at=_dt(row.created_at) or datetime.utcnow(),
            last_used=_dt(row.last_used),
            active=bool(row.active),
            user_id=getattr(row, 'user_id', None),
        )

    async def save(self, key: ApiKey) -> None:
        async with self._session() as s:
            await s.execute(api_keys_table.insert().values(
                id=key.id, name=key.name, key_hash=key.key_hash, role=key.role,
                created_at=_ts(key.created_at), last_used=_ts(key.last_used),
                active=int(key.active), user_id=key.user_id,
            ))
            await s.commit()

    async def find_by_hash(self, hash: str) -> ApiKey | None:
        async with self._session() as s:
            row = (await s.execute(select(api_keys_table).where(api_keys_table.c.key_hash == hash))).first()
            return self._to_entity(row) if row else None

    async def find_all(self) -> list[ApiKey]:
        async with self._session() as s:
            rows = (await s.execute(select(api_keys_table).order_by(api_keys_table.c.created_at.desc()))).all()
            return [self._to_entity(r) for r in rows]

    async def revoke(self, id: str) -> None:
        async with self._session() as s:
            await s.execute(update(api_keys_table).where(api_keys_table.c.id == id).values(active=0))
            await s.commit()

    async def revoke_by_user_id(self, user_id: str) -> None:
        async with self._session() as s:
            await s.execute(
                update(api_keys_table)
                .where(api_keys_table.c.user_id == user_id)
                .values(active=0)
            )
            await s.commit()

    async def count_active(self) -> int:
        async with self._session() as s:
            result = await s.execute(
                select(func.count()).select_from(api_keys_table).where(api_keys_table.c.active == 1)
            )
            return result.scalar() or 0

    async def touch_last_used(self, id: str) -> None:
        async with self._session() as s:
            await s.execute(
                update(api_keys_table).where(api_keys_table.c.id == id)
                .values(last_used=datetime.utcnow().isoformat())
            )
            await s.commit()


# ── User Repository ───────────────────────────────────────────────────────────

class UserRepository(IUserRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    def _to_entity(self, row) -> User:
        return User(
            id=row.id,
            username=row.username,
            password_hash=row.password_hash,
            role=row.role or "readonly",
            email=row.email,
            active=bool(row.active),
            created_at=_dt(row.created_at) or datetime.utcnow(),
            last_login=_dt(row.last_login),
        )

    async def save(self, user: User) -> None:
        async with self._session() as s:
            await s.execute(users_table.insert().values(
                id=user.id, username=user.username, password_hash=user.password_hash,
                role=user.role, email=user.email, active=int(user.active),
                created_at=_ts(user.created_at), last_login=_ts(user.last_login),
            ))
            await s.commit()

    async def find_by_id(self, id: str) -> User | None:
        async with self._session() as s:
            row = (await s.execute(select(users_table).where(users_table.c.id == id))).first()
            return self._to_entity(row) if row else None

    async def find_by_username(self, username: str) -> User | None:
        async with self._session() as s:
            row = (await s.execute(select(users_table).where(users_table.c.username == username))).first()
            return self._to_entity(row) if row else None

    async def find_all(self) -> list[User]:
        async with self._session() as s:
            rows = (await s.execute(select(users_table).order_by(users_table.c.created_at))).all()
            return [self._to_entity(r) for r in rows]

    async def update(self, user: User) -> None:
        async with self._session() as s:
            await s.execute(
                update(users_table).where(users_table.c.id == user.id).values(
                    username=user.username, password_hash=user.password_hash,
                    role=user.role, email=user.email, active=int(user.active),
                    last_login=_ts(user.last_login),
                )
            )
            await s.commit()

    async def count_active(self) -> int:
        async with self._session() as s:
            result = await s.execute(
                select(func.count()).select_from(users_table).where(users_table.c.active == 1)
            )
            return result.scalar() or 0


# ── Audit Repository ──────────────────────────────────────────────────────────

class AuditRepository(IAuditRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    async def save(self, entry: dict) -> None:
        async with self._session() as s:
            await s.execute(audit_log_table.insert().values(**entry))
            await s.commit()

    async def find_recent(self, limit: int) -> list[dict]:
        async with self._session() as s:
            rows = (await s.execute(
                select(audit_log_table).order_by(audit_log_table.c.id.desc()).limit(limit)
            )).all()
            return [dict(r._mapping) for r in rows]


# ── Rule Repository ───────────────────────────────────────────────────────────

class RuleRepository(IRuleRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    def _to_entity(self, row) -> Rule:
        return Rule(
            id=row.id,
            control_id=row.control_id,
            name=row.name,
            description=row.description,
            remediation_notes=row.remediation_notes,
            active=bool(row.active),
            frameworks=json.loads(row.frameworks or "[]"),
            code_blocks=json.loads(row.code_blocks or "{}"),
            inspec_blocks=json.loads(row.inspec_blocks or "{}"),
            created_at=_dt(row.created_at) or datetime.utcnow(),
            updated_at=_dt(row.updated_at) or datetime.utcnow(),
        )

    def _to_dict(self, rule: Rule) -> dict:
        return {
            "id": rule.id, "control_id": rule.control_id, "name": rule.name,
            "description": rule.description, "remediation_notes": rule.remediation_notes,
            "active": int(rule.active), "frameworks": json.dumps(rule.frameworks),
            "code_blocks": json.dumps(rule.code_blocks), "inspec_blocks": json.dumps(rule.inspec_blocks),
            "created_at": _ts(rule.created_at), "updated_at": _ts(rule.updated_at),
        }

    async def save(self, rule: Rule) -> None:
        async with self._session() as s:
            await s.execute(rules_table.insert().values(**self._to_dict(rule)))
            await s.commit()

    async def find_by_id(self, id: str) -> Rule | None:
        async with self._session() as s:
            row = (await s.execute(select(rules_table).where(rules_table.c.id == id))).first()
            return self._to_entity(row) if row else None

    async def find_by_control_id(self, cid: str) -> Rule | None:
        async with self._session() as s:
            row = (await s.execute(select(rules_table).where(rules_table.c.control_id == cid))).first()
            return self._to_entity(row) if row else None

    async def find_all(self, filters: dict) -> list[Rule]:
        async with self._session() as s:
            rows = (await s.execute(select(rules_table).order_by(rules_table.c.created_at.desc()))).all()
            entities = [self._to_entity(r) for r in rows]
            if filters.get("active") is not None:
                entities = [e for e in entities if e.active == filters["active"]]
            if filters.get("framework"):
                entities = [e for e in entities if any(f["framework"] == filters["framework"] for f in e.frameworks)]
            if filters.get("os_family"):
                entities = [e for e in entities if e.code_blocks.get(filters["os_family"])]
            return entities

    async def update(self, rule: Rule) -> None:
        async with self._session() as s:
            await s.execute(update(rules_table).where(rules_table.c.id == rule.id).values(**self._to_dict(rule)))
            await s.commit()

    async def delete(self, id: str) -> None:
        async with self._session() as s:
            await s.execute(delete(rules_table).where(rules_table.c.id == id))
            await s.commit()


# ── Platform Config Repository ────────────────────────────────────────────────

class PlatformConfigRepository(IPlatformConfigRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    async def get(self, key: str) -> str | None:
        async with self._session() as s:
            row = (await s.execute(
                select(platform_config_table).where(platform_config_table.c.key == key)
            )).first()
            return row.value if row else None

    async def set(self, key: str, value: str) -> None:
        async with self._session() as s:
            existing = (await s.execute(
                select(platform_config_table).where(platform_config_table.c.key == key)
            )).first()
            ts = datetime.utcnow().isoformat()
            if existing:
                await s.execute(
                    update(platform_config_table)
                    .where(platform_config_table.c.key == key)
                    .values(value=value, updated_at=ts)
                )
            else:
                await s.execute(
                    platform_config_table.insert().values(key=key, value=value, updated_at=ts)
                )
            await s.commit()

    async def get_all(self) -> dict[str, str]:
        async with self._session() as s:
            rows = (await s.execute(select(platform_config_table))).all()
            return {r.key: r.value for r in rows}
