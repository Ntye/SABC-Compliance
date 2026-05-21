from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime

from core.domain.entities import Job, Node
from core.domain.interfaces import (
    IJobRepository, INodeRepository, IPlatformConfigRepository,
)
from core.errors import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


async def _test_tcp(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


class GetInfrastructureStatusUseCase:
    def __init__(
        self,
        config_repo: IPlatformConfigRepository,
        puppet_master_host_env: str | None,
        wazuh_manager_host_env: str | None,
        puppet_port: int,
        wazuh_port: int,
    ) -> None:
        self._config = config_repo
        self._puppet_env = puppet_master_host_env
        self._wazuh_env = wazuh_manager_host_env
        self._puppet_port = puppet_port
        self._wazuh_port = wazuh_port

    async def execute(self) -> dict:
        puppet_host = await self._config.get("puppet_master_host") or self._puppet_env
        wazuh_host = await self._config.get("wazuh_manager_host") or self._wazuh_env

        puppet_reachable, wazuh_reachable = await asyncio.gather(
            _test_tcp(puppet_host, self._puppet_port) if puppet_host else asyncio.sleep(0, result=None),
            _test_tcp(wazuh_host, self._wazuh_port) if wazuh_host else asyncio.sleep(0, result=None),
        )

        return {
            "puppet": {
                "configured": bool(puppet_host),
                "host": puppet_host,
                "port": self._puppet_port,
                "reachable": puppet_reachable,
            },
            "wazuh": {
                "configured": bool(wazuh_host),
                "host": wazuh_host,
                "port": self._wazuh_port,
                "reachable": wazuh_reachable,
            },
        }


class SetMasterHostUseCase:
    def __init__(
        self,
        config_repo: IPlatformConfigRepository,
        puppet_port: int,
        wazuh_port: int,
    ) -> None:
        self._config = config_repo
        self._puppet_port = puppet_port
        self._wazuh_port = wazuh_port

    async def execute(self, service: str, host: str) -> dict:
        if service not in ("puppet", "wazuh"):
            raise ValidationError("service must be 'puppet' or 'wazuh'")
        host = host.strip()
        if not host:
            raise ValidationError("host is required")

        key = "puppet_master_host" if service == "puppet" else "wazuh_manager_host"
        port = self._puppet_port if service == "puppet" else self._wazuh_port

        await self._config.set(key, host)
        reachable = await _test_tcp(host, port)
        return {"service": service, "host": host, "port": port, "reachable": reachable}


class StartJobUseCase:
    def __init__(
        self,
        job_repo: IJobRepository,
        node_repo: INodeRepository,
        ansible_adapter,
        ws_manager,
    ) -> None:
        self._job_repo = job_repo
        self._node_repo = node_repo
        self._ansible = ansible_adapter
        self._ws = ws_manager

    async def execute(self, data: dict) -> Job:
        node_id = data.get("node_id")
        on_complete = data.get("on_complete")

        node: Node | None = None
        if node_id:
            node = await self._node_repo.find_by_id(node_id)
            if not node:
                raise NotFoundError(f"Node '{node_id}' not found")

        now = datetime.utcnow()
        job = Job(
            id=str(uuid.uuid4()),
            type=data.get("type", "provision"),
            status="pending",
            node_id=node.id if node else None,
            target_group=node.hostname if node else "all",
            playbook=data.get("playbook", "provision.yml"),
            extra_vars=data.get("extra_vars", {}),
            created_at=now,
            updated_at=now,
        )
        await self._job_repo.save(job)
        asyncio.create_task(self._run(job, node, on_complete))
        return job

    async def _run(self, job: Job, node: Node | None, on_complete) -> None:
        job.start()
        await self._job_repo.update(job)

        async def on_line(line: str) -> None:
            entry = {"ts": datetime.utcnow().isoformat(), "level": "info", "line": line}
            await self._job_repo.append_log(job.id, entry)
            await self._ws.broadcast(job.id, entry)

        try:
            exit_code = await self._ansible.run_playbook(
                job_id=job.id,
                node=node,
                playbook=job.playbook,
                extra_vars=job.extra_vars,
                on_line=on_line,
            )
            if exit_code == 0:
                job.succeed(exit_code)
            else:
                job.fail(exit_code)
        except Exception as exc:
            logger.error("Job %s failed: %s", job.id, exc)
            await on_line(f"FATAL: {exc}")
            job.fail(1)

        job.updated_at = datetime.utcnow()
        await self._job_repo.update(job)

        done_entry = {
            "ts": datetime.utcnow().isoformat(),
            "level": "system",
            "line": f"── Job {job.status.upper()} (exit {job.exit_code}) ──",
        }
        await self._job_repo.append_log(job.id, done_entry)
        await self._ws.broadcast(job.id, done_entry)

        if on_complete:
            try:
                await on_complete(job, node)
            except Exception as exc:
                logger.error("on_complete callback failed for job %s: %s", job.id, exc)


class ListJobsUseCase:
    def __init__(self, job_repo: IJobRepository) -> None:
        self._repo = job_repo

    async def execute(self, limit: int = 50) -> list[Job]:
        return await self._repo.find_all(limit)


class GetJobUseCase:
    def __init__(self, job_repo: IJobRepository) -> None:
        self._repo = job_repo

    async def execute(self, job_id: str) -> Job:
        job = await self._repo.find_by_id(job_id)
        if not job:
            raise NotFoundError(f"Job '{job_id}' not found")
        return job


class CancelJobUseCase:
    def __init__(self, job_repo: IJobRepository, ansible_adapter) -> None:
        self._repo = job_repo
        self._ansible = ansible_adapter

    async def execute(self, job_id: str) -> Job:
        job = await self._repo.find_by_id(job_id)
        if not job:
            raise NotFoundError(f"Job '{job_id}' not found")
        if not job.is_terminal():
            self._ansible.cancel(job_id)
            job.cancel()
            job.updated_at = datetime.utcnow()
            await self._repo.update(job)
        return job


class InstallServiceUseCase:
    """
    Install puppet-master, wazuh-manager, puppet-agent, or wazuh-agent
    on a registered node via an Ansible job.

    On success:
      - puppet_master / wazuh_manager: saves node IP to platform_config
      - puppet_agent / wazuh_agent: marks node.puppet_enrolled / wazuh_enrolled
    """

    _PLAYBOOKS = {
        "puppet_master": "install_puppet_master.yml",
        "wazuh_manager": "install_wazuh_manager.yml",
        "puppet_agent":  "install_puppet_agent.yml",
        "wazuh_agent":   "install_wazuh_agent.yml",
    }
    _CONFIG_KEYS = {
        "puppet_master": "puppet_master_host",
        "wazuh_manager": "wazuh_manager_host",
    }
    _ENROLL_ATTRS = {
        "puppet_agent": "puppet_enrolled",
        "wazuh_agent":  "wazuh_enrolled",
    }

    def __init__(
        self,
        start_job_uc: StartJobUseCase,
        config_repo: IPlatformConfigRepository,
        node_repo: INodeRepository,
        service: str,
    ) -> None:
        if service not in self._PLAYBOOKS:
            raise ValueError(f"Unknown service: {service}")
        self._start = start_job_uc
        self._config = config_repo
        self._node_repo = node_repo
        self._service = service

    async def execute(self, node_id: str) -> Job:
        node = await self._node_repo.find_by_id(node_id)
        if not node:
            raise NotFoundError(f"Node '{node_id}' not found")

        config_key = self._CONFIG_KEYS.get(self._service)
        enroll_attr = self._ENROLL_ATTRS.get(self._service)
        node_ip = node.ip
        node_repo = self._node_repo
        config_repo = self._config

        async def on_complete(job: Job, _node: Node | None) -> None:
            if job.status != "success":
                return
            if config_key:
                await config_repo.set(config_key, node_ip)
            if enroll_attr:
                fresh = await node_repo.find_by_id(node_id)
                if fresh:
                    setattr(fresh, enroll_attr, True)
                    fresh.updated_at = datetime.utcnow()
                    await node_repo.update(fresh)

        return await self._start.execute({
            "type": f"install_{self._service}",
            "node_id": node_id,
            "playbook": self._PLAYBOOKS[self._service],
            "extra_vars": {},
            "on_complete": on_complete,
        })
