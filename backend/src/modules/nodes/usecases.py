from __future__ import annotations
import asyncio
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
