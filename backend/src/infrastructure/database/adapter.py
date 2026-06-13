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
    ApiKey, ComplianceReport, Job, Node, NodeGroup, Profile, ProfileControl,
    RemediationEvent, Rule, User, UserGroup,
)
from core.domain.interfaces import (
    IApiKeyRepository, IAuditRepository, IComplianceRepository,
    IJobRepository, INodeGroupRepository, INodeRepository, IPlatformConfigRepository,
    IProfileRepository, IRuleRepository, IUserRepository, IUserGroupRepository,
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
    Column("profile", Text),
    Column("duration", Text),
    Column("skipped_checks", Integer, default=0),
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


profiles_table = Table(
    "profiles", metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("description", Text),
    Column("os_family", Text, default="linux"),
    Column("version", Text, default="1.0.0"),
    Column("source", Text, default="custom"),
    Column("created_at", Text),
    Column("updated_at", Text),
)


profile_controls_table = Table(
    "profile_controls", metadata,
    Column("id", Text, primary_key=True),
    Column("profile_id", Text, nullable=False),
    Column("section_id", Text, nullable=False),
    Column("section", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("position", Integer, default=0),
    Column("kind", Text, default="control"),
    Column("cis_id", Text),
    Column("description", Text),
    Column("recommended_value", Text),
    Column("agreed_value", Text),
    Column("risk_profile", Text),
    Column("rationale", Text),
    Column("validate_guideline", Text),
    Column("configure_guideline", Text),
    Column("regulatory", Text),
    Column("notes", Text),
    Column("check_command", Text),
    Column("enabled", Integer, default=1),
    Column("created_at", Text),
    Column("updated_at", Text),
)

profile_control_history_table = Table(
    "profile_control_history", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("control_id", Text, nullable=False),
    Column("snapshot", Text, nullable=False),
    Column("saved_at", Text, nullable=False),
)


user_groups_table = Table(
    "user_groups", metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False, unique=True),
    Column("description", Text),
    Column("role", Text, default="readonly"),
    Column("permissions", Text, default="[]"),
    Column("is_default", Integer, default=0),
    Column("created_at", Text),
    Column("updated_at", Text),
)

user_group_members_table = Table(
    "user_group_members", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("group_id", Text, nullable=False),
    Column("user_id", Text, nullable=False),
)

node_groups_table = Table(
    "node_groups", metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False, unique=True),
    Column("description", Text),
    Column("parent", Text),
    Column("environment", Text),
    Column("is_environment_group", Integer, default=0),
    Column("match_type", Text),
    Column("rules", Text),
    Column("puppet_group_id", Text),
    Column("wazuh_synced", Integer, default=0),
    Column("puppet_synced", Integer, default=0),
    Column("created_at", Text),
    Column("updated_at", Text),
)

node_group_nodes_table = Table(
    "node_group_nodes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("group_id", Text, nullable=False),
    Column("node_id", Text, nullable=False),
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
        try:
            await conn.execute(text("ALTER TABLE profile_controls ADD COLUMN check_command TEXT"))
        except Exception:
            pass  # column already exists
        # jobs.logs was a JSON blob that suffered a write-race; now replaced by
        # the job_logs table.  Drop the old column if it exists (SQLite workaround:
        # we just leave it — SQLite ignored unused columns and doesn't support
        # DROP COLUMN before 3.35, so we simply stop writing/reading it).

        # User groups — migrations for new columns
        for col, typ in [("description", "TEXT"), ("role", "TEXT"),
                         ("permissions", "TEXT"), ("is_default", "INTEGER")]:
            try:
                await conn.execute(text(f"ALTER TABLE user_groups ADD COLUMN {col} {typ}"))
            except Exception:
                pass

        # Node groups — migrations for Puppet-style classification columns
        for col, typ in [("parent", "TEXT"), ("environment", "TEXT"),
                         ("is_environment_group", "INTEGER"),
                         ("match_type", "TEXT"), ("rules", "TEXT")]:
            try:
                await conn.execute(text(f"ALTER TABLE node_groups ADD COLUMN {col} {typ}"))
            except Exception:
                pass

        # Compliance reports — migrations for structured InSpec scan output
        for col, typ in [("profile", "TEXT"), ("duration", "TEXT"),
                         ("skipped_checks", "INTEGER")]:
            try:
                await conn.execute(text(f"ALTER TABLE compliance_reports ADD COLUMN {col} {typ}"))
            except Exception:
                pass

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
            profile=getattr(row, "profile", None),
            duration=(float(row.duration) if getattr(row, "duration", None) else None),
            skipped_checks=getattr(row, "skipped_checks", None) or 0,
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
                profile=report.profile,
                duration=(str(report.duration) if report.duration is not None else None),
                skipped_checks=report.skipped_checks,
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
                            "skipped_checks": r.skipped_checks, "profile": r.profile,
                            "duration": r.duration, "severity_counts": r.severity_counts,
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


# ── Profile Repository ────────────────────────────────────────────────────────

class ProfileRepository(IProfileRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    # ── mapping ──
    def _control_to_entity(self, row) -> ProfileControl:
        return ProfileControl(
            id=row.id,
            profile_id=row.profile_id,
            section_id=row.section_id,
            section=row.section,
            title=row.title,
            position=row.position or 0,
            kind=getattr(row, "kind", None) or "control",
            cis_id=row.cis_id,
            description=row.description,
            recommended_value=row.recommended_value,
            agreed_value=row.agreed_value,
            risk_profile=row.risk_profile,
            rationale=row.rationale,
            validate_guideline=row.validate_guideline,
            configure_guideline=row.configure_guideline,
            regulatory=row.regulatory,
            notes=row.notes,
            check_command=getattr(row, "check_command", None),
            enabled=bool(row.enabled),
            created_at=_dt(row.created_at) or datetime.utcnow(),
            updated_at=_dt(row.updated_at) or datetime.utcnow(),
        )

    def _control_to_dict(self, c: ProfileControl) -> dict:
        return {
            "id": c.id, "profile_id": c.profile_id, "section_id": c.section_id,
            "section": c.section, "title": c.title, "position": c.position,
            "kind": c.kind, "cis_id": c.cis_id, "description": c.description,
            "recommended_value": c.recommended_value, "agreed_value": c.agreed_value,
            "risk_profile": c.risk_profile, "rationale": c.rationale,
            "validate_guideline": c.validate_guideline,
            "configure_guideline": c.configure_guideline,
            "regulatory": c.regulatory, "notes": c.notes,
            "check_command": c.check_command,
            "enabled": int(c.enabled),
            "created_at": _ts(c.created_at), "updated_at": _ts(c.updated_at),
        }

    def _profile_to_entity(self, row, controls: list[ProfileControl]) -> Profile:
        return Profile(
            id=row.id,
            name=row.name,
            description=row.description,
            os_family=row.os_family or "linux",
            version=row.version or "1.0.0",
            source=row.source or "custom",
            controls=controls,
            created_at=_dt(row.created_at) or datetime.utcnow(),
            updated_at=_dt(row.updated_at) or datetime.utcnow(),
        )

    def _profile_to_dict(self, p: Profile) -> dict:
        return {
            "id": p.id, "name": p.name, "description": p.description,
            "os_family": p.os_family, "version": p.version, "source": p.source,
            "created_at": _ts(p.created_at), "updated_at": _ts(p.updated_at),
        }

    async def _controls_for(self, s, profile_id: str) -> list[ProfileControl]:
        rows = (await s.execute(
            select(profile_controls_table)
            .where(profile_controls_table.c.profile_id == profile_id)
            .order_by(profile_controls_table.c.position)
        )).all()
        return [self._control_to_entity(r) for r in rows]

    # ── profiles ──
    async def save(self, profile: Profile) -> None:
        async with self._session() as s:
            await s.execute(profiles_table.insert().values(**self._profile_to_dict(profile)))
            for c in profile.controls:
                await s.execute(profile_controls_table.insert().values(**self._control_to_dict(c)))
            await s.commit()

    async def find_by_id(self, id: str) -> Profile | None:
        async with self._session() as s:
            row = (await s.execute(select(profiles_table).where(profiles_table.c.id == id))).first()
            if not row:
                return None
            controls = await self._controls_for(s, id)
            return self._profile_to_entity(row, controls)

    async def find_all(self) -> list[Profile]:
        async with self._session() as s:
            rows = (await s.execute(
                select(profiles_table).order_by(profiles_table.c.created_at)
            )).all()
            out: list[Profile] = []
            for row in rows:
                controls = await self._controls_for(s, row.id)
                out.append(self._profile_to_entity(row, controls))
            return out

    async def update(self, profile: Profile) -> None:
        async with self._session() as s:
            await s.execute(
                update(profiles_table).where(profiles_table.c.id == profile.id)
                .values(**self._profile_to_dict(profile))
            )
            await s.commit()

    async def delete(self, id: str) -> None:
        async with self._session() as s:
            await s.execute(delete(profile_controls_table).where(profile_controls_table.c.profile_id == id))
            await s.execute(delete(profiles_table).where(profiles_table.c.id == id))
            await s.commit()

    # ── controls ──
    async def save_control(self, control: ProfileControl) -> None:
        async with self._session() as s:
            await s.execute(profile_controls_table.insert().values(**self._control_to_dict(control)))
            await s.commit()

    async def update_control(self, control: ProfileControl) -> None:
        async with self._session() as s:
            await s.execute(
                update(profile_controls_table).where(profile_controls_table.c.id == control.id)
                .values(**self._control_to_dict(control))
            )
            await s.commit()

    async def find_control(self, control_id: str) -> ProfileControl | None:
        async with self._session() as s:
            row = (await s.execute(
                select(profile_controls_table).where(profile_controls_table.c.id == control_id)
            )).first()
            return self._control_to_entity(row) if row else None

    async def delete_control(self, control_id: str) -> None:
        async with self._session() as s:
            await s.execute(delete(profile_controls_table).where(profile_controls_table.c.id == control_id))
            await s.commit()

    async def search_controls(self, query: str, limit: int = 40) -> list[ProfileControl]:
        async with self._session() as s:
            q = f"%{query.lower()}%"
            stmt = (
                select(profile_controls_table)
                .where(
                    (func.lower(profile_controls_table.c.title).like(q)) |
                    (func.lower(profile_controls_table.c.section_id).like(q)) |
                    (func.lower(profile_controls_table.c.section).like(q)) |
                    (func.lower(profile_controls_table.c.cis_id).like(q))
                )
                .where(profile_controls_table.c.kind == "control")
                .order_by(profile_controls_table.c.section_id)
                .limit(limit)
            )
            rows = (await s.execute(stmt)).all()
            return [self._control_to_entity(r) for r in rows]

    async def save_control_history(self, control_id: str, snapshot: str) -> None:
        async with self._session() as s:
            await s.execute(profile_control_history_table.insert().values(
                control_id=control_id,
                snapshot=snapshot,
                saved_at=datetime.utcnow().isoformat(),
            ))
            await s.commit()

    async def get_control_history(self, control_id: str) -> list[dict]:
        async with self._session() as s:
            rows = (await s.execute(
                select(profile_control_history_table)
                .where(profile_control_history_table.c.control_id == control_id)
                .order_by(profile_control_history_table.c.id.desc())
                .limit(50)
            )).all()
            return [{"id": r.id, "snapshot": r.snapshot, "saved_at": r.saved_at} for r in rows]


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


# ── UserGroup Repository ──────────────────────────────────────────────────────

class UserGroupRepository(IUserGroupRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    async def _members(self, session, group_id: str) -> list[str]:
        rows = (await session.execute(
            select(user_group_members_table.c.user_id)
            .where(user_group_members_table.c.group_id == group_id)
        )).all()
        return [r.user_id for r in rows]

    def _to_entity(self, row, member_ids: list[str] | None = None) -> UserGroup:
        return UserGroup(
            id=row.id, name=row.name, description=row.description,
            permissions=json.loads(getattr(row, 'permissions', None) or "[]"),
            is_default=bool(getattr(row, 'is_default', 0)),
            member_ids=member_ids or [],
            created_at=_dt(row.created_at) or datetime.utcnow(),
            updated_at=_dt(row.updated_at) or datetime.utcnow(),
        )

    async def save(self, group: UserGroup) -> None:
        async with self._session() as s:
            await s.execute(user_groups_table.insert().values(
                id=group.id, name=group.name, description=group.description,
                permissions=json.dumps(group.permissions),
                is_default=int(group.is_default),
                created_at=_ts(group.created_at), updated_at=_ts(group.updated_at),
            ))
            await s.commit()

    async def find_by_id(self, id: str) -> UserGroup | None:
        async with self._session() as s:
            row = (await s.execute(select(user_groups_table).where(user_groups_table.c.id == id))).first()
            if not row:
                return None
            members = await self._members(s, id)
            return self._to_entity(row, members)

    async def find_by_name(self, name: str) -> UserGroup | None:
        async with self._session() as s:
            row = (await s.execute(select(user_groups_table).where(user_groups_table.c.name == name))).first()
            if not row:
                return None
            members = await self._members(s, row.id)
            return self._to_entity(row, members)

    async def find_all(self) -> list[UserGroup]:
        async with self._session() as s:
            rows = (await s.execute(select(user_groups_table).order_by(
                user_groups_table.c.is_default.desc(),
                user_groups_table.c.created_at
            ))).all()
            result = []
            for row in rows:
                members = await self._members(s, row.id)
                result.append(self._to_entity(row, members))
            return result

    async def update(self, group: UserGroup) -> None:
        async with self._session() as s:
            await s.execute(
                update(user_groups_table).where(user_groups_table.c.id == group.id).values(
                    name=group.name, description=group.description,
                    permissions=json.dumps(group.permissions),
                    updated_at=_ts(group.updated_at),
                )
            )
            await s.commit()

    async def delete(self, id: str) -> None:
        async with self._session() as s:
            await s.execute(delete(user_group_members_table).where(user_group_members_table.c.group_id == id))
            await s.execute(delete(user_groups_table).where(user_groups_table.c.id == id))
            await s.commit()

    async def add_member(self, group_id: str, user_id: str) -> None:
        async with self._session() as s:
            existing = (await s.execute(
                select(user_group_members_table)
                .where(user_group_members_table.c.group_id == group_id)
                .where(user_group_members_table.c.user_id == user_id)
            )).first()
            if not existing:
                await s.execute(user_group_members_table.insert().values(group_id=group_id, user_id=user_id))
                await s.commit()

    async def remove_member(self, group_id: str, user_id: str) -> None:
        async with self._session() as s:
            await s.execute(
                delete(user_group_members_table)
                .where(user_group_members_table.c.group_id == group_id)
                .where(user_group_members_table.c.user_id == user_id)
            )
            await s.commit()


# ── NodeGroup Repository ──────────────────────────────────────────────────────

class NodeGroupRepository(INodeGroupRepository):
    def __init__(self, session: async_sessionmaker) -> None:
        self._session = session

    async def _node_ids(self, session, group_id: str) -> list[str]:
        rows = (await session.execute(
            select(node_group_nodes_table.c.node_id)
            .where(node_group_nodes_table.c.group_id == group_id)
        )).all()
        return [r.node_id for r in rows]

    def _to_entity(self, row, node_ids: list[str] | None = None) -> NodeGroup:
        return NodeGroup(
            id=row.id,
            name=row.name,
            description=row.description,
            parent=getattr(row, "parent", None) or "All Nodes",
            environment=getattr(row, "environment", None) or "production",
            is_environment_group=bool(getattr(row, "is_environment_group", 0)),
            match_type=getattr(row, "match_type", None) or "all",
            rules=json.loads(getattr(row, "rules", None) or "[]"),
            node_ids=node_ids or [],
            puppet_group_id=row.puppet_group_id,
            wazuh_synced=bool(row.wazuh_synced),
            puppet_synced=bool(row.puppet_synced),
            created_at=_dt(row.created_at) or datetime.utcnow(),
            updated_at=_dt(row.updated_at) or datetime.utcnow(),
        )

    async def save(self, g: NodeGroup) -> None:
        async with self._session() as s:
            await s.execute(node_groups_table.insert().values(
                id=g.id, name=g.name, description=g.description,
                parent=g.parent, environment=g.environment,
                is_environment_group=int(g.is_environment_group),
                match_type=g.match_type, rules=json.dumps(g.rules),
                puppet_group_id=g.puppet_group_id,
                wazuh_synced=int(g.wazuh_synced),
                puppet_synced=int(g.puppet_synced),
                created_at=_ts(g.created_at),
                updated_at=_ts(g.updated_at),
            ))
            await s.commit()

    async def find_by_id(self, id: str) -> NodeGroup | None:
        async with self._session() as s:
            row = (await s.execute(select(node_groups_table).where(node_groups_table.c.id == id))).first()
            if not row:
                return None
            node_ids = await self._node_ids(s, id)
            return self._to_entity(row, node_ids)

    async def find_by_name(self, name: str) -> NodeGroup | None:
        async with self._session() as s:
            row = (await s.execute(select(node_groups_table).where(node_groups_table.c.name == name))).first()
            if not row:
                return None
            node_ids = await self._node_ids(s, row.id)
            return self._to_entity(row, node_ids)

    async def find_all(self) -> list[NodeGroup]:
        async with self._session() as s:
            rows = (await s.execute(select(node_groups_table).order_by(node_groups_table.c.created_at))).all()
            result = []
            for row in rows:
                node_ids = await self._node_ids(s, row.id)
                result.append(self._to_entity(row, node_ids))
            return result

    async def update(self, g: NodeGroup) -> None:
        async with self._session() as s:
            await s.execute(
                update(node_groups_table).where(node_groups_table.c.id == g.id).values(
                    name=g.name, description=g.description,
                    parent=g.parent, environment=g.environment,
                    is_environment_group=int(g.is_environment_group),
                    match_type=g.match_type, rules=json.dumps(g.rules),
                    puppet_group_id=g.puppet_group_id,
                    wazuh_synced=int(g.wazuh_synced),
                    puppet_synced=int(g.puppet_synced),
                    updated_at=_ts(g.updated_at),
                )
            )
            await s.commit()

    async def delete(self, id: str) -> None:
        async with self._session() as s:
            await s.execute(delete(node_group_nodes_table).where(node_group_nodes_table.c.group_id == id))
            await s.execute(delete(node_groups_table).where(node_groups_table.c.id == id))
            await s.commit()

    async def add_node(self, group_id: str, node_id: str) -> None:
        async with self._session() as s:
            existing = (await s.execute(
                select(node_group_nodes_table)
                .where(node_group_nodes_table.c.group_id == group_id)
                .where(node_group_nodes_table.c.node_id == node_id)
            )).first()
            if not existing:
                await s.execute(node_group_nodes_table.insert().values(group_id=group_id, node_id=node_id))
                await s.commit()

    async def remove_node(self, group_id: str, node_id: str) -> None:
        async with self._session() as s:
            await s.execute(
                delete(node_group_nodes_table)
                .where(node_group_nodes_table.c.group_id == group_id)
                .where(node_group_nodes_table.c.node_id == node_id)
            )
            await s.commit()
