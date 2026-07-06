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
        puppet_port: int,
    ) -> None:
        self._config = config_repo
        self._puppet_env = puppet_master_host_env
        self._puppet_port = puppet_port

    async def execute(self) -> dict:
        puppet_host = await self._config.get("puppet_master_host") or self._puppet_env
        puppet_reachable = await _test_tcp(puppet_host, self._puppet_port) if puppet_host else None

        return {
            "puppet": {
                "configured": bool(puppet_host),
                "host": puppet_host,
                "port": self._puppet_port,
                "reachable": puppet_reachable,
            },
        }


class SetMasterHostUseCase:
    def __init__(
        self,
        config_repo: IPlatformConfigRepository,
        puppet_port: int,
    ) -> None:
        self._config = config_repo
        self._puppet_port = puppet_port

    async def execute(self, service: str, host: str) -> dict:
        if service != "puppet":
            raise ValidationError("service must be 'puppet'")
        host = host.strip()
        if not host:
            raise ValidationError("host is required")

        await self._config.set("puppet_master_host", host)
        reachable = await _test_tcp(host, self._puppet_port)

        return {"service": service, "host": host, "port": self._puppet_port, "reachable": reachable}


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
    Install puppet-master, puppet-agent, or the detection agent on a registered
    node via an Ansible job.

    On success:
      - puppet_master: saves node IP to platform_config
      - puppet_agent / detection_agent: marks node.puppet_enrolled /
        node.detection_enrolled
    """

    _PLAYBOOKS = {
        "puppet_master":           "install_puppet_master.yml",
        "puppet_agent":            "install_puppet_agent.yml",
        # Custom lightweight detection agent (replaces the old wazuh-agent).
        "detection_agent":         "install_detection_agent.yml",
        "check_health":            "check_node_health.yml",
        # One-time: enable the External Node Classifier on a Puppet Core master
        # (node_terminus = exec + external_nodes in puppet.conf, restart server).
        "puppet_core_enc":         "configure_puppet_core_enc.yml",
        # Deploy the sabc_compliance Puppet module to the master + enforce the
        # referential fleet-wide (site-manifest include). Runs on the master node.
        "compliance_module":       "deploy_compliance_module.yml",
    }
    _CONFIG_KEYS = {
        "puppet_master":           "puppet_master_host",
    }
    _ENROLL_ATTRS = {
        "puppet_agent":            "puppet_enrolled",
        "detection_agent":         "detection_enrolled",
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

    async def execute(self, node_id: str, dashboard_port: int | None = None) -> Job:
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
        elif self._service == "detection_agent":
            extra_vars.update(await self._detection_agent_vars(node))
        elif self._service == "puppet_core_enc":
            settings = get_settings()
            extra_vars["enc_dir"] = settings.puppet_core_enc_dir
        elif self._service == "compliance_module":
            import os as _os
            settings = get_settings()
            # The module ships alongside the ansible dir in the image
            # (…/ansible and …/puppet/modules/sabc_compliance share a parent).
            base = _os.path.dirname(_os.path.abspath(settings.ansible_dir or "/app/ansible"))
            extra_vars["sabc_module_src"] = _os.path.join(base, "puppet", "modules", "sabc_compliance")
        elif self._service == "check_health":
            host = await self._config.get("puppet_master_host")
            if host:
                extra_vars["puppet_master_host"] = host

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

    async def _detection_agent_vars(self, node: Node) -> dict:
        """Assemble the variables install_detection_agent.yml needs.

        The gateway URL is derived from PLATFORM_PUBLIC_HOST / HOST_IP just like
        the compliance module deploy; the shared webhook API key is read from
        platform_config and auto-generated on first use so the whole flow works
        without manual secret plumbing.
        """
        import os
        import secrets

        settings = get_settings()
        public_host = (
            os.environ.get("PLATFORM_PUBLIC_HOST", "").strip()
            or os.environ.get("HOST_IP", "").strip()
            or settings.host_ip
        )
        if not public_host:
            raise ValidationError(
                "Cannot derive the platform webhook URL: set PLATFORM_PUBLIC_HOST "
                "(or HOST_IP) so managed nodes can reach the detection gateway."
            )
        try:
            https_port = int(os.environ.get("HTTPS_PORT", "8443") or "8443")
        except ValueError:
            https_port = 8443

        api_key = (
            await self._config.get("detection_webhook_api_key")
            or settings.detection_webhook_api_key
        )
        if not api_key:
            api_key = "sabcdet_" + secrets.token_urlsafe(32)
        # Persist so the webhook receiver and every future agent install agree.
        await self._config.set("detection_webhook_api_key", api_key)

        # Agent sources live in backend/detection-agent (a sibling of the ansible
        # dir); the Docker image copies them to /app/detection-agent and the dev
        # compose bind-mounts them to the same path.
        candidates = [
            os.path.join(
                os.path.dirname(os.path.abspath(settings.ansible_dir or "/app/ansible")),
                "detection-agent",
            ),
            "/app/detection-agent",
        ]
        src = next((c for c in candidates if os.path.isdir(c)), candidates[-1])

        return {
            "detection_gateway_url": f"https://{public_host}:{https_port}/api/webhooks/detection",
            "detection_api_key": api_key,
            "detection_node_hostname": node.hostname,
            "detection_agent_src": src,
        }


class SwitchPuppetEditionUseCase:
    """Switch the Puppet master between Enterprise (PE Advanced) and Core.

    One action does the whole switch:
      1. records the new edition in platform config (so node-group sync routes to
         the right classifier — RBAC/NC API for PE, ENC for Core);
      2. (re)installs the master with the chosen edition via
         install_puppet_master.yml, purging the opposite edition first (PE and
         Core cannot coexist);
      3. for Core, configures the External Node Classifier on the master once
         puppetserver is up, so classification works immediately.

    Switching regenerates the master CA, so agents must re-enroll afterwards.
    """

    def __init__(self, start_job_uc, config_repo, node_repo, configure_enc_uc=None):
        self._start = start_job_uc
        self._config = config_repo
        self._node_repo = node_repo
        self._configure_enc = configure_enc_uc

    async def execute(self, node_id: str, target_edition: str) -> Job:
        edition = (target_edition or "").strip().lower()
        if edition not in ("enterprise", "core"):
            raise ValidationError("edition must be 'enterprise' or 'core'")
        node = await self._node_repo.find_by_id(node_id)
        if not node:
            raise NotFoundError(f"Node '{node_id}' not found")

        # Persist the edition up front so a sync that races the install still
        # targets the right backend (it no-ops gracefully until the master is up).
        await self._config.set("puppet_edition", edition)

        extra_vars: dict = {"puppet_edition": edition, "purge_other_edition": True}
        if edition == "enterprise":
            pw = await self._config.get("pe_console_password")
            if pw:
                extra_vars["pe_console_password"] = pw

        config_repo = self._config
        node_ip = node.ip
        configure_enc = self._configure_enc

        async def on_complete(job: Job, _node: Node | None) -> None:
            if job.status != "success":
                return
            await config_repo.set("puppet_master_host", node_ip)
            # For Core, enable the ENC on the freshly-installed master.
            if edition == "core" and configure_enc is not None:
                try:
                    await configure_enc.execute(node_id)
                except Exception:
                    pass

        return await self._start.execute({
            "type": f"switch_puppet_{edition}",
            "node_id": node_id,
            "playbook": "install_puppet_master.yml",
            "extra_vars": extra_vars,
            "on_complete": on_complete,
        })


class DetectAgentsUseCase:
    """Launch a read-only Ansible job that detects Puppet / detection-agent
    enrollment.

    Requires become: yes on the target to read protected cert directories. On
    success, updates node.puppet_enrolled / detection_enrolled by scanning the
    job log for PUPPET_STATUS=ENROLLED / DETECTION_STATUS=ENROLLED sentinel
    strings output by detect_agents.yml.
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
            fresh.puppet_enrolled    = "PUPPET_STATUS=ENROLLED"    in all_text
            fresh.detection_enrolled = "DETECTION_STATUS=ENROLLED" in all_text
            fresh.updated_at = datetime.utcnow()
            await node_repo.update(fresh)

        return await self._start.execute({
            "type":       "detect_agents",
            "node_id":    node_id,
            "playbook":   self.PLAYBOOK,
            "extra_vars": {},
            "on_complete": on_complete,
        })


class ScanEngineUseCase:
    """Manages the platform-side (controller) scan engine (CINC Auditor) installation.

    The scan engine is agentless: it lives once on the SABC platform server and
    reaches each registered node over SSH. This use case answers two questions:
      1. Is the scan engine installed on the controller? (and at what version)
      2. Can the scan engine reach a given node over SSH? (which marks the
         node as scan_ready = True so the compliance engine can run controls).
    """

    SCAN_BIN = "/usr/bin/cinc-auditor"

    def __init__(self, node_repo: INodeRepository, default_ssh_key_path: str) -> None:
        self._node_repo = node_repo
        self._default_key = default_ssh_key_path

    async def get_status(self) -> dict:
        """Return {installed, version, executable_path}."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.SCAN_BIN, "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode == 0:
                version = stdout.decode().strip().splitlines()[0] if stdout else "unknown"
                return {"installed": True, "version": version, "executable_path": self.SCAN_BIN}
        except (FileNotFoundError, asyncio.TimeoutError, Exception):
            pass
        return {"installed": False, "version": None, "executable_path": self.SCAN_BIN}

    async def install_on_controller(self) -> dict:
        """Install CINC Auditor on the platform server via the CINC omnitruck script.

        Requires root (typical inside the backend container). On bare-metal
        deploys without root, returns an error with the manual install command.
        """
        cmd = "curl -sL https://omnitruck.cinc.sh/install.sh | bash -s -- -P cinc-auditor"
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

        We use plain SSH for the reachability check: the scan engine uses the
        same SSH channel that Ansible already uses, so if SSH works the
        controller can run compliance controls against the node.
        """
        node = await self._node_repo.find_by_id(node_id)
        if not node:
            raise NotFoundError(f"Node '{node_id}' not found")

        # Check scan engine installation status separately from SSH reachability.
        scan_status = await self.get_status()

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
            "echo SCAN_REACHABLE",
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
            ok = proc.returncode == 0 and "SCAN_REACHABLE" in out
            output = (out + "\n" + err).strip() if not ok else None
        except asyncio.TimeoutError:
            ok = False
            output = "ssh timed out after 20s"
        except Exception as exc:
            ok = False
            output = str(exc)

        # Always persist — the user's expectation is "click verify, see the
        # current truth", so we record this run's result unconditionally.
        node.scan_ready = ok
        node.updated_at = datetime.utcnow()
        await self._node_repo.update(node)

        result: dict = {
            "node_id": node_id,
            "hostname": node.hostname,
            "reachable": ok,
            "output": output[-1500:] if output else None,
        }
        if not scan_status["installed"]:
            result["error"] = (
                "CINC Auditor n'est pas installé sur la plateforme — "
                "cliquez « Installer sur la plateforme » pour activer les scans de conformité."
            )
        return result

    async def verify_all_nodes(self) -> dict:
        """Probe every registered node in parallel; persist per-node results."""
        status = await self.get_status()
        if not status["installed"]:
            return {
                "controller": status,
                "error": "Scan engine is not installed on the platform",
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
