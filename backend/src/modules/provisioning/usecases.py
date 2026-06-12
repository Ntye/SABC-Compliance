from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime

from core.domain.entities import Job, Node
from core.domain.interfaces import (
    IJobRepository, INodeRepository, IPlatformConfigRepository,
)
from config import get_settings
from core.errors import ConflictError, NotFoundError, ValidationError

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
        "check_health":  "check_node_health.yml",
    }
    _CONFIG_KEYS = {
        "puppet_master": "puppet_master_host",
        "wazuh_manager": "wazuh_manager_host",
    }
    _ENROLL_ATTRS = {
        "puppet_agent":  "puppet_enrolled",
        "wazuh_manager": "wazuh_enrolled",
        "wazuh_agent":   "wazuh_enrolled",
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

        enroll_attr = self._ENROLL_ATTRS.get(self._service)
        if enroll_attr and getattr(node, enroll_attr, False):
            raise ConflictError(
                f"Node '{node.hostname}' is already enrolled for {self._service}. "
                "Remove the node and re-register to force re-installation."
            )

        config_key = self._CONFIG_KEYS.get(self._service)
        node_ip = node.ip
        node_repo = self._node_repo
        config_repo = self._config

        extra_vars: dict = {}
        if self._service == "puppet_master":
            pw = await self._config.get("pe_console_password")
            if pw:
                extra_vars["pe_console_password"] = pw
        elif self._service == "puppet_agent":
            host = await self._config.get("puppet_master_host")
            if host:
                extra_vars["puppet_master_host"] = host
        elif self._service == "wazuh_agent":
            host = await self._config.get("wazuh_manager_host")
            if host:
                extra_vars["wazuh_manager_host"] = host
            settings = get_settings()
            extra_vars["wazuh_api_user"] = settings.wazuh_api_user
            if settings.wazuh_api_pass:
                extra_vars["wazuh_api_pass"] = settings.wazuh_api_pass
            extra_vars["wazuh_api_port"] = settings.wazuh_api_port
        elif self._service == "check_health":
            host = await self._config.get("puppet_master_host")
            if host:
                extra_vars["puppet_master_host"] = host
            host = await self._config.get("wazuh_manager_host")
            if host:
                extra_vars["wazuh_manager_host"] = host

        pe_password_used = extra_vars.get("pe_console_password", "SABCPuppet1!")

        async def on_complete(job: Job, _node: Node | None) -> None:
            if job.status != "success":
                return
            if config_key:
                await config_repo.set(config_key, node_ip)
            if self._service == "puppet_master":
                await config_repo.set("pe_console_password", pe_password_used)
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
            "extra_vars": extra_vars,
            "on_complete": on_complete,
        })


class DetectAgentsUseCase:
    """Launch a read-only Ansible job that detects Puppet / Wazuh enrollment.

    Requires become: yes on the target to read protected cert directories and
    Wazuh logs. On success, updates node.puppet_enrolled / wazuh_enrolled by
    scanning the job log for PUPPET_STATUS=ENROLLED / WAZUH_STATUS=ENROLLED
    sentinel strings output by detect_agents.yml.
    """

    PLAYBOOK = "detect_agents.yml"

    def __init__(
        self,
        start_job_uc: StartJobUseCase,
        node_repo: INodeRepository,
        job_repo: IJobRepository,
    ) -> None:
        self._start    = start_job_uc
        self._node_repo = node_repo
        self._job_repo  = job_repo

    async def execute(self, node_id: str) -> Job:
        node = await self._node_repo.find_by_id(node_id)
        if not node:
            raise NotFoundError(f"Node '{node_id}' not found")

        node_repo = self._node_repo
        job_repo  = self._job_repo

        async def on_complete(job: Job, _node: Node | None) -> None:
            if job.status != "success":
                return
            full_job = await job_repo.find_by_id(job.id)
            if not full_job:
                return
            all_text = " ".join(entry.get("line", "") for entry in full_job.logs)
            fresh = await node_repo.find_by_id(node_id)
            if not fresh:
                return
            fresh.puppet_enrolled = "PUPPET_STATUS=ENROLLED" in all_text
            fresh.wazuh_enrolled  = "WAZUH_STATUS=ENROLLED"  in all_text
            fresh.updated_at = datetime.utcnow()
            await node_repo.update(fresh)

        return await self._start.execute({
            "type":       "detect_agents",
            "node_id":    node_id,
            "playbook":   self.PLAYBOOK,
            "extra_vars": {},
            "on_complete": on_complete,
        })


class InspecControllerUseCase:
    """Manages the platform-side (controller) InSpec installation.

    InSpec is agentless: it lives once on the SABC platform server and reaches
    each registered node over SSH. This use case answers two questions:
      1. Is InSpec installed on the controller? (and at what version)
      2. Can InSpec actually reach a given node over SSH? (which marks the
         node as inspec_installed = True so the compliance engine knows it
         can run controls against it).
    """

    INSPEC_BIN = "/usr/bin/inspec"

    def __init__(self, node_repo: INodeRepository, default_ssh_key_path: str) -> None:
        self._node_repo = node_repo
        self._default_key = default_ssh_key_path

    async def get_status(self) -> dict:
        """Return {installed, version, executable_path}."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.INSPEC_BIN, "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode == 0:
                version = stdout.decode().strip().splitlines()[0] if stdout else "unknown"
                return {"installed": True, "version": version, "executable_path": self.INSPEC_BIN}
        except (FileNotFoundError, asyncio.TimeoutError, Exception):
            pass
        return {"installed": False, "version": None, "executable_path": self.INSPEC_BIN}

    async def install_on_controller(self) -> dict:
        """Install InSpec on the platform server via the official omnitruck script.

        Requires root (typical inside the backend container). On bare-metal
        deploys without root, returns an error with the manual install command.
        """
        cmd = "curl -sL https://omnitruck.chef.io/install.sh | bash -s -- -P inspec -v 5"
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
            output = stdout.decode(errors="replace") if stdout else ""
            if proc.returncode == 0:
                status = await self.get_status()
                return {"success": True, "output": output[-2000:], **status}
            return {
                "success": False,
                "output": output[-2000:],
                "error": f"installer exited with code {proc.returncode}",
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": "installer timed out after 5 minutes"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def verify_node(self, node_id: str) -> dict:
        """Probe a single node over SSH and persist the result.

        We deliberately use plain SSH (not `inspec detect`) for the reachability
        check: InSpec runs over the same SSH channel that Ansible already uses,
        so if SSH works the controller can drive InSpec controls. Plain SSH
        also sidesteps InSpec's Ruby Net::SSH host-key check (which doesn't
        honor the container's defaults on first connect) and the Chef license
        prompt entirely.
        """
        node = await self._node_repo.find_by_id(node_id)
        if not node:
            raise NotFoundError(f"Node '{node_id}' not found")

        # Check InSpec installation status separately from SSH reachability.
        # The SSH test below doesn't need InSpec — it just verifies the channel
        # that InSpec would use. We always run it so the badge reflects reality.
        inspec_status = await self.get_status()

        key = node.ssh_key_path or self._default_key
        args = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-i", key,
            "-p", str(node.ssh_port),
            f"{node.ssh_user}@{node.ip}",
            "echo INSPEC_REACHABLE",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
            out = (stdout or b"").decode(errors="replace")
            err = (stderr or b"").decode(errors="replace")
            ok = proc.returncode == 0 and "INSPEC_REACHABLE" in out
            output = (out + "\n" + err).strip() if not ok else None
        except asyncio.TimeoutError:
            ok = False
            output = "ssh timed out after 20s"
        except Exception as exc:
            ok = False
            output = str(exc)

        # Always persist — the user's expectation is "click verify, see the
        # current truth", so we record this run's result unconditionally.
        node.inspec_installed = ok
        node.updated_at = datetime.utcnow()
        await self._node_repo.update(node)

        result: dict = {
            "node_id": node_id,
            "hostname": node.hostname,
            "reachable": ok,
            "output": output[-1500:] if output else None,
        }
        if not inspec_status["installed"]:
            result["error"] = (
                "InSpec n'est pas installé sur la plateforme — "
                "cliquez « Installer sur la plateforme » pour activer les scans de conformité."
            )
        return result

    async def verify_all_nodes(self) -> dict:
        """Probe every registered node in parallel; persist per-node results."""
        status = await self.get_status()
        if not status["installed"]:
            return {
                "controller": status,
                "error": "InSpec is not installed on the platform",
                "results": [],
            }

        nodes = await self._node_repo.find_all({})
        results = await asyncio.gather(
            *(self.verify_node(n.id) for n in nodes),
            return_exceptions=True,
        )
        normalized = [
            r if isinstance(r, dict)
            else {"node_id": None, "reachable": False, "error": str(r)}
            for r in results
        ]
        reachable = sum(1 for r in normalized if r.get("reachable"))
        return {
            "controller": status,
            "total": len(nodes),
            "reachable": reachable,
            "results": normalized,
        }
