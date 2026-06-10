from __future__ import annotations
import asyncio
import os
import re
import socket
import uuid
from datetime import datetime

from core.domain.entities import Node
from core.domain.interfaces import IEventBus, INodeRepository, ISSHClient, IPlatformConfigRepository
from core.errors import ConflictError, NotFoundError, SSHConnectError, ValidationError
from core.events import Events


async def _resolve_node(repo: INodeRepository, id_or_hostname: str) -> Node:
    node = await repo.find_by_id(id_or_hostname)
    if not node:
        node = await repo.find_by_hostname(id_or_hostname)
    if not node:
        raise NotFoundError(f"Node '{id_or_hostname}' not found")
    return node


async def _check_dns_local(hostname: str, expected_ip: str) -> bool:
    """Check whether this machine can resolve hostname to expected_ip."""
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            None, lambda: socket.getaddrinfo(hostname, None)
        )
        return any(r[4][0] == expected_ip for r in results)
    except Exception:
        return False


async def _noop() -> None:
    return None


async def _check_dns_remote(ssh: ISSHClient, node: Node, target_hostname: str) -> bool | None:
    """SSH into node and check whether it can resolve target_hostname."""
    cmd = f"getent hosts {target_hostname} > /dev/null 2>&1 && echo DNS_OK || echo DNS_FAIL"
    stdout, _, rc = await ssh.run_command(
        node.ip, node.ssh_port, node.ssh_user, node.ssh_key_path, cmd
    )
    if "DNS_OK" in stdout:
        return True
    if "DNS_FAIL" in stdout:
        return False
    return None


class RegisterNodeUseCase:
    def __init__(self, node_repository: INodeRepository, ssh_client: ISSHClient, event_bus: IEventBus) -> None:
        self._repo = node_repository
        self._ssh = ssh_client
        self._bus = event_bus

    async def execute(self, data: dict) -> Node:
        hostname = data.get("hostname", "").strip()
        ip = data.get("ip", "").strip()
        if not hostname or not ip:
            raise ValidationError("hostname and ip are required")

        existing = await self._repo.find_by_hostname(hostname)
        if existing:
            raise ConflictError(f"Node '{hostname}' is already registered")

        ssh_port = int(data.get("ssh_port", 22))
        ssh_user = data.get("ssh_user", "ansible")
        ssh_key_path = data.get("ssh_key_path") or None

        ok, error = await self._ssh.test_connectivity(ip, ssh_port, ssh_user, ssh_key_path)
        if not ok:
            raise SSHConnectError(error or "SSH connection failed")

        os_family, os_name, os_version = await self._detect_os(ip, ssh_port, ssh_user, ssh_key_path)
        fqdn = await self._get_fqdn(ip, ssh_port, ssh_user, ssh_key_path)
        dns_resolves = await _check_dns_local(hostname, ip)

        now = datetime.utcnow()
        node = Node(
            id=str(uuid.uuid4()),
            hostname=hostname,
            ip=ip,
            ssh_port=ssh_port,
            ssh_user=ssh_user,
            ssh_key_path=ssh_key_path,
            os_family=os_family,
            os_name=os_name,
            os_version=os_version,
            fqdn=fqdn,
            dns_resolves=dns_resolves,
            description=data.get("description"),
            tags=data.get("tags", []),
            status="reachable",
            last_seen=now,
            created_at=now,
            updated_at=now,
        )
        await self._repo.save(node)

        # Best-effort: detect existing agent installations and mark as enrolled.
        # A failure here never blocks registration — the node is already saved.
        try:
            detect_cmd = (
                # Puppet: binary present AND has a signed node cert (not just ca.pem)
                "if test -f /opt/puppetlabs/puppet/bin/puppet && "
                "find /etc/puppetlabs/puppet/ssl/certs -maxdepth 1 -name '*.pem' "
                "! -name 'ca.pem' 2>/dev/null | grep -q .; "
                "then echo PUPPET_OK; else echo PUPPET_MISSING; fi; "
                # Wazuh: agentd binary present AND has successfully connected
                "if test -f /var/ossec/bin/wazuh-agentd && "
                "grep -aq 'Connected to the server' /var/ossec/logs/ossec.log 2>/dev/null; "
                "then echo WAZUH_OK; else echo WAZUH_MISSING; fi"
            )
            stdout, _, _ = await self._ssh.run_command(
                ip, ssh_port, ssh_user, ssh_key_path, detect_cmd
            )
            puppet_found = "PUPPET_OK" in stdout
            wazuh_found  = "WAZUH_OK" in stdout
            if puppet_found or wazuh_found:
                node.puppet_enrolled = puppet_found
                node.wazuh_enrolled  = wazuh_found
                node.updated_at = datetime.utcnow()
                await self._repo.update(node)
        except Exception:
            pass

        self._bus.publish(Events.NODE_REGISTERED, {"node_id": node.id, "hostname": node.hostname})
        return node

    async def _detect_os(self, ip: str, port: int, user: str, key_path: str | None) -> tuple[str, str | None, str | None]:
        stdout, _, exit_code = await self._ssh.run_command(ip, port, user, key_path, "cat /etc/os-release")
        if exit_code != 0:
            return "Unknown", None, None

        fields: dict[str, str] = {}
        for line in stdout.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                fields[k.strip()] = v.strip().strip('"')

        id_val = fields.get("ID", "").lower()
        id_like = fields.get("ID_LIKE", "").lower()
        combined = f"{id_val} {id_like}"

        if re.search(r"rhel|centos|rocky|almalinux|fedora", combined):
            os_family = "RedHat"
        elif re.search(r"debian|ubuntu", combined):
            os_family = "Debian"
        else:
            os_family = "Unknown"

        os_name = fields.get("PRETTY_NAME") or fields.get("NAME")
        os_version = fields.get("VERSION_ID")
        return os_family, os_name, os_version

    async def _get_fqdn(self, ip: str, port: int, user: str, key_path: str | None) -> str | None:
        stdout, _, _ = await self._ssh.run_command(
            ip, port, user, key_path, "hostname -f 2>/dev/null || hostname"
        )
        fqdn = stdout.strip()
        return fqdn if fqdn else None


class GetNodeUseCase:
    def __init__(self, node_repository: INodeRepository) -> None:
        self._repo = node_repository

    async def execute(self, id_or_hostname: str) -> Node:
        return await _resolve_node(self._repo, id_or_hostname)


class ListNodesUseCase:
    def __init__(self, node_repository: INodeRepository) -> None:
        self._repo = node_repository

    async def execute(self, filters: dict) -> list[Node]:
        return await self._repo.find_all(filters)


class PingNodeUseCase:
    def __init__(self, node_repository: INodeRepository, ssh_client: ISSHClient) -> None:
        self._repo = node_repository
        self._ssh = ssh_client

    async def execute(self, id_or_hostname: str) -> dict:
        node = await _resolve_node(self._repo, id_or_hostname)
        loop = asyncio.get_event_loop()
        start = loop.time()
        ok, error = await self._ssh.test_connectivity(
            node.ip, node.ssh_port, node.ssh_user, node.ssh_key_path
        )
        latency_ms = round((loop.time() - start) * 1000, 1)
        if ok:
            node.mark_reachable()
            node.dns_resolves = await _check_dns_local(node.hostname, node.ip)
        else:
            node.mark_unreachable()
        node.updated_at = datetime.utcnow()
        await self._repo.update(node)
        return {
            "hostname": node.hostname,
            "ip": node.ip,
            "reachable": ok,
            "latency_ms": latency_ms if ok else None,
            "error": error,
            "status": node.status,
            "dns_resolves": node.dns_resolves,
        }


class PingAllNodesUseCase:
    def __init__(self, node_repository: INodeRepository, ssh_client: ISSHClient) -> None:
        self._repo = node_repository
        self._ssh = ssh_client

    async def execute(self) -> dict:
        nodes = await self._repo.find_all({})

        async def _ping(node: Node) -> tuple[Node, bool]:
            ok, _ = await self._ssh.test_connectivity(node.ip, node.ssh_port, node.ssh_user, node.ssh_key_path)
            if ok:
                node.mark_reachable()
                node.dns_resolves = await _check_dns_local(node.hostname, node.ip)
            else:
                node.mark_unreachable()
            node.updated_at = datetime.utcnow()
            return node, ok

        results = await asyncio.gather(*[_ping(n) for n in nodes], return_exceptions=True)

        reachable = 0
        unreachable = 0
        errors = 0
        updated: list[Node] = []
        for r in results:
            if isinstance(r, Exception):
                errors += 1
            else:
                node, ok = r
                updated.append(node)
                if ok:
                    reachable += 1
                else:
                    unreachable += 1

        await asyncio.gather(*[self._repo.update(n) for n in updated], return_exceptions=True)
        return {"total": len(nodes), "reachable": reachable, "unreachable": unreachable, "errors": errors}


class CheckNodeDnsUseCase:
    """
    Multi-directional DNS check for a node:
      1. backend → node hostname  (this machine resolves the node)
      2. node → backend hostname  (node resolves the platform server)
      3. node → puppet master     (node can reach Puppet by name — required for agent enrollment)
      4. node → wazuh manager     (node can reach Wazuh by name — required for agent enrollment)
    """
    def __init__(
        self,
        node_repository: INodeRepository,
        ssh_client: ISSHClient,
        platform_config: IPlatformConfigRepository,
        puppet_master_host_env: str | None = None,
        wazuh_manager_host_env: str | None = None,
    ) -> None:
        self._repo = node_repository
        self._ssh = ssh_client
        self._config = platform_config
        self._puppet_env = puppet_master_host_env
        self._wazuh_env = wazuh_manager_host_env

    async def execute(self, id_or_hostname: str) -> dict:
        node = await _resolve_node(self._repo, id_or_hostname)
        backend_hostname = socket.gethostname()

        puppet_host = await self._config.get("puppet_master_host") or self._puppet_env
        wazuh_host  = await self._config.get("wazuh_manager_host") or self._wazuh_env

        backend_to_node, node_to_backend, node_to_puppet, node_to_wazuh = await asyncio.gather(
            _check_dns_local(node.hostname, node.ip),
            _check_dns_remote(self._ssh, node, backend_hostname),
            _check_dns_remote(self._ssh, node, puppet_host) if puppet_host else _noop(),
            _check_dns_remote(self._ssh, node, wazuh_host)  if wazuh_host  else _noop(),
        )

        node.dns_resolves = backend_to_node
        node.updated_at = datetime.utcnow()
        await self._repo.update(node)

        checks = {
            "backend_to_node": {
                "ok": backend_to_node,
                "from": backend_hostname,
                "to": node.hostname,
                "description": "Platform server resolves this node's hostname",
            },
            "node_to_backend": {
                "ok": node_to_backend,
                "from": node.hostname,
                "to": backend_hostname,
                "description": "Node resolves the platform server's hostname",
            },
            "node_to_puppet": {
                "ok": node_to_puppet,
                "from": node.hostname,
                "to": puppet_host,
                "description": "Node resolves the Puppet master hostname (required for agent enrollment)",
            },
            "node_to_wazuh": {
                "ok": node_to_wazuh,
                "from": node.hostname,
                "to": wazuh_host,
                "description": "Node resolves the Wazuh manager hostname (required for agent enrollment)",
            },
        }
        all_ok = all(
            v["ok"] is True
            for v in checks.values()
            if v["to"] is not None
        )
        return {
            "node_id": node.id,
            "hostname": node.hostname,
            "ip": node.ip,
            "fqdn": node.fqdn,
            "checks": checks,
            "all_ok": all_ok,
        }


class UpdateNodeUseCase:
    def __init__(self, node_repository: INodeRepository) -> None:
        self._repo = node_repository

    async def execute(self, id_or_hostname: str, updates: dict) -> Node:
        node = await _resolve_node(self._repo, id_or_hostname)
        allowed = {"hostname", "description", "tags", "ssh_port", "ssh_user", "ssh_key_path"}
        for k, v in updates.items():
            if k in allowed and v is not None:
                setattr(node, k, v)
        node.updated_at = datetime.utcnow()
        await self._repo.update(node)
        return node


class DeleteNodeUseCase:
    def __init__(self, node_repository: INodeRepository) -> None:
        self._repo = node_repository

    async def execute(self, id_or_hostname: str) -> dict:
        node = await _resolve_node(self._repo, id_or_hostname)
        await self._repo.delete(node.id)
        return {"message": f"Node '{node.hostname}' deleted", "id": node.id}


class FixNodeDnsUseCase:
    """
    Automatically apply /etc/hosts fixes for failed DNS checks:
      - backend_to_node:  appends node IP → hostname to the platform container's /etc/hosts
      - node_to_backend:  SSHes to node as ansible user and appends platform IP → hostname
      - node_to_puppet:   SSHes to node and appends puppet master IP → hostname
      - node_to_wazuh:    SSHes to node and appends wazuh manager IP → hostname
    """

    def __init__(
        self,
        node_repository: INodeRepository,
        ssh_client: ISSHClient,
        platform_config: IPlatformConfigRepository,
        puppet_master_host_env: str | None = None,
        wazuh_manager_host_env: str | None = None,
    ) -> None:
        self._repo = node_repository
        self._ssh = ssh_client
        self._config = platform_config
        self._puppet_env = puppet_master_host_env
        self._wazuh_env = wazuh_manager_host_env

    async def execute(self, id_or_hostname: str, checks: list[str]) -> dict:
        node = await _resolve_node(self._repo, id_or_hostname)
        puppet_host = await self._config.get("puppet_master_host") or self._puppet_env
        wazuh_host  = await self._config.get("wazuh_manager_host") or self._wazuh_env

        results: dict[str, dict] = {}

        if "backend_to_node" in checks:
            results["backend_to_node"] = await self._fix_platform_to_node(node)

        if "node_to_backend" in checks:
            results["node_to_backend"] = await self._fix_node_to_platform(node)

        if "node_to_puppet" in checks and puppet_host:
            results["node_to_puppet"] = await self._fix_node_to_remote_host(node, puppet_host)

        if "node_to_wazuh" in checks and wazuh_host:
            results["node_to_wazuh"] = await self._fix_node_to_remote_host(node, wazuh_host)

        return results

    async def _fix_platform_to_node(self, node: Node) -> dict:
        """Append IP → hostname entry to the platform container's /etc/hosts."""
        parts = [node.ip, node.hostname]
        if node.fqdn and node.fqdn != node.hostname:
            parts.append(node.fqdn)
        entry = "  ".join(parts)
        try:
            proc = await asyncio.create_subprocess_exec(
                "tee", "-a", "/etc/hosts",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate(input=f"\n{entry}\n".encode())
            if proc.returncode == 0:
                return {"ok": True, "entry": entry}
            return {"ok": False, "error": "tee exited with non-zero status"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _fix_node_to_platform(self, node: Node) -> dict:
        """
        Determine the platform's IP as seen from the node (via SSH_CLIENT) then
        append the mapping to the node's /etc/hosts via the ansible user.
        """
        platform_ip = await self._platform_ip_from_node(node)
        if not platform_ip:
            return {"ok": False, "error": "Cannot determine platform IP reachable from node"}
        backend_hostname = socket.gethostname()
        entry = f"{platform_ip}  {backend_hostname}"
        return await self._append_to_node_hosts(node, entry)

    async def _fix_node_to_remote_host(self, node: Node, target_host: str) -> dict:
        """
        Resolve target_host from the platform (it can reach it), then append
        the IP → hostname mapping to the node's /etc/hosts via the ansible user.
        """
        target_ip = await self._resolve_ip(target_host)
        if not target_ip:
            return {"ok": False, "error": f"Platform cannot resolve {target_host}"}
        entry = f"{target_ip}  {target_host}"
        return await self._append_to_node_hosts(node, entry)

    async def _append_to_node_hosts(self, node: Node, entry: str) -> dict:
        cmd = f"echo '{entry}' | sudo tee -a /etc/hosts"
        try:
            _, stderr, rc = await self._ssh.run_command(
                node.ip, node.ssh_port, node.ssh_user, node.ssh_key_path, cmd
            )
            if rc == 0:
                return {"ok": True, "entry": entry}
            return {"ok": False, "error": (stderr or "").strip() or "Non-zero exit code"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _platform_ip_from_node(self, node: Node) -> str | None:
        # When we SSH to the node, $SSH_CLIENT contains the source (platform) IP
        try:
            stdout, _, _ = await self._ssh.run_command(
                node.ip, node.ssh_port, node.ssh_user, node.ssh_key_path,
                "echo $SSH_CLIENT"
            )
            parts = stdout.strip().split()
            if parts and parts[0]:
                return parts[0]
        except Exception:
            pass
        # Fallback: explicit HOST_IP env var
        return os.environ.get("HOST_IP", "").strip() or None

    async def _resolve_ip(self, hostname: str) -> str | None:
        loop = asyncio.get_event_loop()
        try:
            results = await loop.run_in_executor(
                None, lambda: socket.getaddrinfo(hostname, None)
            )
            return results[0][4][0] if results else None
        except Exception:
            return None


class ChangeNodeIdentityUseCase:
    """
    Safely change a node's IP address and/or hostname (DNS name) and replicate
    the change across the platform's records and /etc/hosts mappings.

    Designed for the EC2 case where a stop/start assigns a new public IP and
    public DNS name. The change is validated BEFORE anything is committed:

      1. Preflight — SSH-test the NEW ip (or current ip) with existing creds.
         If the server is not reachable at the new address, abort cleanly and
         leave everything untouched.
      2. Uniqueness — reject a hostname already used by another node.
      3. Apply (only after preflight passes):
         a. Rewrite the platform container's /etc/hosts: drop stale lines for
            the old ip/hostname, add `new_ip  new_hostname [fqdn]`.
         b. (opt-in) Rename the server's system hostname via hostnamectl.
         c. Re-detect the FQDN and re-check DNS resolution.
         d. Persist ip/hostname/fqdn to the database (done last).
      4. Warn — if the node is Puppet/Wazuh enrolled, the agent identity is
         bound to the old hostname; report that re-enrollment is required.
    """

    def __init__(self, node_repository: INodeRepository, ssh_client: ISSHClient) -> None:
        self._repo = node_repository
        self._ssh = ssh_client

    async def execute(self, id_or_hostname: str, data: dict) -> dict:
        node = await _resolve_node(self._repo, id_or_hostname)

        old_ip = node.ip
        old_hostname = node.hostname
        old_fqdn = node.fqdn

        new_ip = (data.get("ip") or "").strip() or old_ip
        new_hostname = (data.get("hostname") or "").strip() or old_hostname
        apply_system_hostname = bool(data.get("apply_system_hostname", False))

        if new_ip == old_ip and new_hostname == old_hostname and not apply_system_hostname:
            raise ValidationError("Nothing to change — provide a new IP or hostname")

        # ── 2. Uniqueness ────────────────────────────────────────────────────
        if new_hostname != old_hostname:
            clash = await self._repo.find_by_hostname(new_hostname)
            if clash and clash.id != node.id:
                raise ConflictError(f"Hostname '{new_hostname}' is already registered to another node")

        # ── 1. Preflight: the new address must be reachable over SSH ──────────
        ok, error = await self._ssh.test_connectivity(
            new_ip, node.ssh_port, node.ssh_user, node.ssh_key_path
        )
        if not ok:
            raise SSHConnectError(
                f"Cannot reach the server at {new_ip} over SSH — aborting, nothing was changed. "
                f"({error or 'connection failed'})"
            )

        warnings: list[str] = []
        steps: dict[str, dict] = {}

        # ── 3b. (opt-in) rename the server's system hostname ─────────────────
        if apply_system_hostname and new_hostname != old_hostname:
            steps["system_hostname"] = await self._set_system_hostname(node, new_ip, new_hostname)

        # ── 3c. re-detect FQDN from the (possibly renamed) server ────────────
        new_fqdn = await self._get_fqdn(node, new_ip) or (
            new_hostname if new_hostname != old_hostname else old_fqdn
        )

        # ── 3a. rewrite the platform container's /etc/hosts mapping ──────────
        steps["platform_hosts"] = await self._rewrite_platform_hosts(
            remove_tokens=[old_ip, old_hostname] + ([old_fqdn] if old_fqdn else []),
            new_ip=new_ip,
            new_hostname=new_hostname,
            new_fqdn=new_fqdn,
        )

        # ── 3d. persist to the database (last) ───────────────────────────────
        node.ip = new_ip
        node.hostname = new_hostname
        node.fqdn = new_fqdn
        node.dns_resolves = await _check_dns_local(new_hostname, new_ip)
        node.mark_reachable()
        node.updated_at = datetime.utcnow()
        await self._repo.update(node)

        # ── 4. enrollment warnings ───────────────────────────────────────────
        if node.puppet_enrolled and new_hostname != old_hostname:
            warnings.append(
                "Puppet agent certificate is bound to the old hostname. Re-enroll the "
                "Puppet agent (clean the old cert on the master, then re-run enrollment)."
            )
        if node.wazuh_enrolled and new_hostname != old_hostname:
            warnings.append(
                "Wazuh agent name is bound to the old hostname. Re-enroll the Wazuh agent "
                "so the manager registers it under the new name."
            )

        return {
            "node_id": node.id,
            "changed": {
                "ip": {"from": old_ip, "to": new_ip} if new_ip != old_ip else None,
                "hostname": {"from": old_hostname, "to": new_hostname} if new_hostname != old_hostname else None,
                "fqdn": {"from": old_fqdn, "to": new_fqdn} if new_fqdn != old_fqdn else None,
            },
            "steps": steps,
            "dns_resolves": node.dns_resolves,
            "warnings": warnings,
            "node": node,
        }

    async def _set_system_hostname(self, node: Node, ip: str, new_hostname: str) -> dict:
        # Set the hostname and keep a 127.0.1.1 loopback entry so sudo/hostname -f
        # keep working immediately, before any DNS propagation.
        short = new_hostname.split(".")[0]
        cmd = (
            f"sudo hostnamectl set-hostname {new_hostname} && "
            f"( grep -q '^127.0.1.1' /etc/hosts "
            f"&& sudo sed -i 's/^127.0.1.1.*/127.0.1.1\\t{new_hostname} {short}/' /etc/hosts "
            f"|| echo '127.0.1.1\\t{new_hostname} {short}' | sudo tee -a /etc/hosts >/dev/null )"
        )
        try:
            _, stderr, rc = await self._ssh.run_command(
                ip, node.ssh_port, node.ssh_user, node.ssh_key_path, cmd
            )
            if rc == 0:
                return {"ok": True}
            return {"ok": False, "error": (stderr or "").strip() or "Non-zero exit code"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _get_fqdn(self, node: Node, ip: str) -> str | None:
        try:
            stdout, _, _ = await self._ssh.run_command(
                ip, node.ssh_port, node.ssh_user, node.ssh_key_path,
                "hostname -f 2>/dev/null || hostname"
            )
            fqdn = stdout.strip()
            return fqdn or None
        except Exception:
            return None

    async def _rewrite_platform_hosts(
        self, remove_tokens: list[str], new_ip: str, new_hostname: str, new_fqdn: str | None
    ) -> dict:
        """Drop stale managed lines, then append the fresh mapping. Idempotent."""
        path = "/etc/hosts"
        tokens = {t for t in remove_tokens if t}
        try:
            loop = asyncio.get_event_loop()

            def _rewrite() -> None:
                try:
                    with open(path, "r") as f:
                        lines = f.readlines()
                except FileNotFoundError:
                    lines = []
                kept = []
                for line in lines:
                    stripped = line.strip()
                    # never touch loopback/localhost lines
                    if not stripped or stripped.startswith("#") or "localhost" in stripped:
                        kept.append(line)
                        continue
                    fields = stripped.split()
                    # drop any line whose ip or any name matches a stale token
                    if any(tok in fields for tok in tokens):
                        continue
                    kept.append(line)
                parts = [new_ip, new_hostname]
                if new_fqdn and new_fqdn not in parts:
                    parts.append(new_fqdn)
                if kept and not kept[-1].endswith("\n"):
                    kept[-1] += "\n"
                kept.append("  ".join(parts) + "\n")
                with open(path, "w") as f:
                    f.writelines(kept)

            await loop.run_in_executor(None, _rewrite)
            return {"ok": True, "entry": "  ".join([new_ip, new_hostname] + ([new_fqdn] if new_fqdn else []))}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
