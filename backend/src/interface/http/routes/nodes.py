from __future__ import annotations
import os
import socket
import subprocess
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.errors import ConflictError, NotFoundError, SSHConnectError, ValidationError
from interface.http.routes.auth import get_current_principal, require_admin, require_operator

router = APIRouter(prefix="/nodes", tags=["Nodes"])

# ── Pydantic models ───────────────────────────────────────────────────────────

class NodeResponse(BaseModel):
    id: str
    hostname: str
    ip: str
    ssh_port: int
    ssh_user: str
    ssh_key_path: str | None = None
    os_family: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    fqdn: str | None = None
    dns_resolves: bool | None = None
    description: str | None = None
    tags: list[str]
    status: str
    puppet_enrolled: bool
    wazuh_enrolled: bool
    inspec_installed: bool
    last_seen: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RegisterNodeRequest(BaseModel):
    hostname: str
    ip: str
    ssh_port: int = 22
    ssh_user: str = "ansible"
    ssh_key_path: str | None = None
    description: str | None = None
    tags: list[str] = []


class UpdateNodeRequest(BaseModel):
    hostname: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    ssh_port: int | None = None
    ssh_user: str | None = None
    ssh_key_path: str | None = None


class DnsCheckEntry(BaseModel):
    ok: bool | None
    from_host: str | None = None
    to: str | None = None
    description: str


class DnsCheckResponse(BaseModel):
    node_id: str
    hostname: str
    ip: str
    fqdn: str | None = None
    checks: dict[str, DnsCheckEntry]
    all_ok: bool


class DnsFixRequest(BaseModel):
    checks: list[str]   # e.g. ["backend_to_node", "node_to_puppet"]


class DnsFixResult(BaseModel):
    results: dict[str, dict]   # check_key → {"ok": bool, "entry"?: str, "error"?: str}


class ChangeIdentityRequest(BaseModel):
    ip: str | None = None
    hostname: str | None = None
    apply_system_hostname: bool = False   # opt-in: also rename the server via hostnamectl


class ChangeIdentityResponse(BaseModel):
    node_id: str
    changed: dict
    steps: dict
    dns_resolves: bool | None = None
    warnings: list[str] = []
    node: NodeResponse


# ── Dependency injection (set by main.py) ─────────────────────────────────────

_register_uc = None
_get_uc = None
_list_uc = None
_ping_uc = None
_ping_all_uc = None
_update_uc = None
_delete_uc = None
_check_dns_uc = None
_fix_dns_uc = None
_change_identity_uc = None


def set_use_cases(
    register_uc, get_uc, list_uc, ping_uc, ping_all_uc,
    update_uc, delete_uc, check_dns_uc, fix_dns_uc, change_identity_uc,
) -> None:
    global _register_uc, _get_uc, _list_uc, _ping_uc, _ping_all_uc
    global _update_uc, _delete_uc, _check_dns_uc, _fix_dns_uc, _change_identity_uc
    _register_uc = register_uc
    _get_uc = get_uc
    _list_uc = list_uc
    _ping_uc = ping_uc
    _ping_all_uc = ping_all_uc
    _update_uc = update_uc
    _delete_uc = delete_uc
    _check_dns_uc = check_dns_uc
    _fix_dns_uc = fix_dns_uc
    _change_identity_uc = change_identity_uc


def _to_response(node) -> NodeResponse:
    return NodeResponse(
        id=node.id,
        hostname=node.hostname,
        ip=node.ip,
        ssh_port=node.ssh_port,
        ssh_user=node.ssh_user,
        ssh_key_path=node.ssh_key_path,
        os_family=node.os_family,
        os_name=node.os_name,
        os_version=node.os_version,
        fqdn=node.fqdn,
        dns_resolves=node.dns_resolves,
        description=node.description,
        tags=node.tags,
        status=node.status,
        puppet_enrolled=node.puppet_enrolled,
        wazuh_enrolled=node.wazuh_enrolled,
        inspec_installed=node.inspec_installed,
        last_seen=node.last_seen,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NodeResponse], summary="List all nodes")
async def list_nodes(
    status: str | None = Query(None),
    os_family: str | None = Query(None),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """List registered nodes with optional status and OS family filters."""
    filters = {}
    if status:
        filters["status"] = status
    if os_family:
        filters["os_family"] = os_family
    nodes = await _list_uc.execute(filters)
    return [_to_response(n) for n in nodes]


@router.post("", response_model=NodeResponse, status_code=201, summary="Register a new node")
async def register_node(
    body: RegisterNodeRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """
    Register a Linux server. Tests SSH connectivity and detects OS before saving.
    Also captures FQDN and checks DNS resolution. Returns 422 if SSH fails.
    """
    try:
        node = await _register_uc.execute(body.model_dump())
        return _to_response(node)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SSHConnectError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/ping-all", summary="Ping all registered nodes")
async def ping_all(principal: AuthPrincipal = Depends(require_operator)):
    """Test SSH connectivity for every registered node concurrently. Also refreshes DNS resolution status."""
    return await _ping_all_uc.execute()


@router.get("/host-info", summary="Return platform host IP, hostname, and admin user")
async def get_host_info(
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """
    Returns the IP, hostname, and detected admin SSH user of the platform host.
    Used by the Add VM page to pre-fill the form when registering this machine.
    Set HOST_IP and HOST_ADMIN_USER in .env for reliable values.
    """
    host_ip = _detect_host_ip()
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = None
    admin_user = _detect_admin_user()
    return {"host_ip": host_ip, "hostname": hostname, "admin_user": admin_user}


@router.get(
    "/setup-script",
    summary="Download the node bootstrap script",
    response_class=PlainTextResponse,
)
async def get_setup_script(
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """
    Returns a downloadable bash script to run on a target server.
    The platform's ansible public key is embedded at download time.

    Transfer to the target server, then run:  sudo bash setup-node.sh
    """
    platform_key = _read_platform_public_key()
    script = _SETUP_SCRIPT_TEMPLATE.replace("__PLATFORM_PUBLIC_KEY__", platform_key)
    return PlainTextResponse(
        content=script,
        headers={"Content-Disposition": 'attachment; filename="setup-node.sh"'},
        media_type="text/x-sh; charset=utf-8",
    )


@router.get(
    "/bootstrap",
    summary="Bootstrap script for curl | sudo bash",
    response_class=PlainTextResponse,
)
async def get_bootstrap_script():
    """
    Unauthenticated endpoint returning the bootstrap script for piping:
        curl -sSL http://<platform>/api/nodes/bootstrap | sudo bash

    Only exposes the platform's public key (not the private key).
    """
    platform_key = _read_platform_public_key()
    script = _SETUP_SCRIPT_TEMPLATE.replace("__PLATFORM_PUBLIC_KEY__", platform_key)
    return PlainTextResponse(content=script, media_type="text/x-sh; charset=utf-8")


@router.get("/{id}", response_model=NodeResponse, summary="Get a node by ID or hostname")
async def get_node(id: str, principal: AuthPrincipal = Depends(get_current_principal)):
    """Retrieve a node by UUID or hostname."""
    try:
        node = await _get_uc.execute(id)
        return _to_response(node)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{id}", response_model=NodeResponse, summary="Update a node")
async def update_node(
    id: str,
    body: UpdateNodeRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Update node metadata (hostname, description, tags, SSH settings)."""
    try:
        node = await _update_uc.execute(id, body.model_dump(exclude_none=True))
        return _to_response(node)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{id}", summary="Delete a node")
async def delete_node(id: str, principal: AuthPrincipal = Depends(require_admin)):
    """Permanently remove a node from the registry (admin only)."""
    try:
        return await _delete_uc.execute(id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{id}/ping", summary="Ping a single node")
async def ping_node(id: str, principal: AuthPrincipal = Depends(require_operator)):
    """Test SSH connectivity for one node, update its status, and refresh DNS resolution."""
    try:
        return await _ping_uc.execute(id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{id}/check-dns", response_model=DnsCheckResponse, summary="Run full multi-directional DNS check")
async def check_node_dns(id: str, principal: AuthPrincipal = Depends(require_operator)):
    """
    Runs four DNS checks:
    - Platform server → node hostname (backend resolves the node)
    - Node → platform server hostname (node resolves the backend)
    - Node → Puppet master hostname (required for Puppet agent enrollment)
    - Node → Wazuh manager hostname (required for Wazuh agent enrollment)

    Updates dns_resolves on the node and returns per-check results with descriptions.
    """
    try:
        result = await _check_dns_uc.execute(id)
        return DnsCheckResponse(
            node_id=result["node_id"],
            hostname=result["hostname"],
            ip=result["ip"],
            fqdn=result["fqdn"],
            checks={
                k: DnsCheckEntry(
                    ok=v["ok"],
                    from_host=v.get("from"),
                    to=v.get("to"),
                    description=v["description"],
                )
                for k, v in result["checks"].items()
            },
            all_ok=result["all_ok"],
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{id}/fix-dns", response_model=DnsFixResult, summary="Auto-apply /etc/hosts fixes for failed DNS checks")
async def fix_node_dns(id: str, body: DnsFixRequest, principal: AuthPrincipal = Depends(require_operator)):
    """
    Applies /etc/hosts entries automatically for each requested check key:
    - backend_to_node:  writes node IP → hostname to the platform's /etc/hosts
    - node_to_backend:  SSHes to node (ansible user) and writes platform IP → hostname
    - node_to_puppet:   SSHes to node and writes puppet master IP → hostname
    - node_to_wazuh:    SSHes to node and writes wazuh manager IP → hostname

    Returns per-check result with ok, entry written, or error message.
    """
    try:
        results = await _fix_dns_uc.execute(id, body.checks)
        return DnsFixResult(results=results)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{id}/change-identity", response_model=ChangeIdentityResponse, summary="Change a node's IP and/or hostname (DNS name) safely")
async def change_node_identity(id: str, body: ChangeIdentityRequest, principal: AuthPrincipal = Depends(require_operator)):
    """
    Change a node's IP address and/or hostname and replicate it everywhere.

    Built for the EC2 case where a stop/start gives the instance a new public IP
    and public DNS name. The new address is SSH-tested BEFORE anything is
    committed — if it is unreachable the call aborts (422) and nothing changes.

    Set `apply_system_hostname=true` to also rename the server itself via
    hostnamectl (opt-in; off by default). Returns the updated node plus any
    warnings (e.g. Puppet/Wazuh agents bound to the old hostname).
    """
    try:
        result = await _change_identity_uc.execute(id, body.model_dump())
        return ChangeIdentityResponse(
            node_id=result["node_id"],
            changed=result["changed"],
            steps=result["steps"],
            dns_resolves=result["dns_resolves"],
            warnings=result["warnings"],
            node=_to_response(result["node"]),
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Host info ─────────────────────────────────────────────────────────────────

def _detect_host_ip() -> str | None:
    """Best-effort detection of the Docker host's IP from inside the container."""
    # 1. Explicit env var (most reliable — set HOST_IP in .env)
    explicit = os.environ.get("HOST_IP", "").strip()
    if explicit:
        return explicit

    # 2. host.docker.internal — resolves via extra_hosts: host-gateway on Linux
    try:
        ip = socket.gethostbyname("host.docker.internal")
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass

    # 3. Default route gateway (Docker bridge IP — valid SSH target if sshd
    #    is bound to 0.0.0.0 on the host)
    try:
        out = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True, timeout=3,
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
    except Exception:
        pass

    return None


def _detect_admin_user() -> str:
    """Return the best-guess SSH admin user for the host machine."""
    # Explicit env var wins
    explicit = os.environ.get("HOST_ADMIN_USER", "").strip()
    if explicit:
        return explicit
    # SUDO_USER is set when someone ran 'sudo docker compose up'
    sudo_user = os.environ.get("SUDO_USER", "").strip()
    if sudo_user and sudo_user != "root":
        return sudo_user
    # USER is the process owner (usually root inside the container,
    # but may be set to the host user via env in docker-compose)
    user = os.environ.get("USER", "").strip()
    if user and user != "root":
        return user
    return "root"


# ── Setup script ──────────────────────────────────────────────────────────────

_SETUP_SCRIPT_TEMPLATE = r"""#!/usr/bin/env bash
# SABC Compliance Platform — Node Bootstrap Script
#
# Run this directly on the target server with root privileges:
#   sudo bash setup-node.sh
#
# Or via curl from the platform:
#   curl -sSL http://<platform-url>/api/nodes/bootstrap | sudo bash
#
# What this script does:
#   1. Creates the 'ansible' OS user
#   2. Installs the platform's SSH public key for passwordless access
#   3. Grants the ansible user full passwordless sudo
#
# After running, register this server in the platform's Node Registry.

set -euo pipefail

SSH_USER="ansible"
PLATFORM_KEY="__PLATFORM_PUBLIC_KEY__"

echo ""
echo "══════════════════════════════════════════════════════"
echo "  SABC Compliance — Node Bootstrap"
echo "  Host: $(hostname -f 2>/dev/null || hostname)"
echo "══════════════════════════════════════════════════════"
echo ""

# ── 1. Create ansible user ──────────────────────────────────────────────────
echo "[1/3] Creating '${SSH_USER}' user ..."
useradd -m -s /bin/bash "${SSH_USER}" 2>/dev/null || true

# ── 2. Install platform SSH key ─────────────────────────────────────────────
echo "[2/3] Installing platform SSH key ..."
mkdir -p /home/"${SSH_USER}"/.ssh
chmod 700 /home/"${SSH_USER}"/.ssh

if ! grep -qF "${PLATFORM_KEY}" /home/"${SSH_USER}"/.ssh/authorized_keys 2>/dev/null; then
  echo "${PLATFORM_KEY}" >> /home/"${SSH_USER}"/.ssh/authorized_keys
fi
chmod 600 /home/"${SSH_USER}"/.ssh/authorized_keys
chown -R "${SSH_USER}":"${SSH_USER}" /home/"${SSH_USER}"/.ssh

# ── 3. Grant passwordless sudo ──────────────────────────────────────────────
echo "[3/3] Granting passwordless sudo ..."
echo "${SSH_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/"${SSH_USER}"
chmod 440 /etc/sudoers.d/"${SSH_USER}"

echo ""
echo "══════════════════════════════════════════════════════"
echo "  Done! This server is ready to be managed."
echo "  Register it now in the platform's Node Registry."
echo "══════════════════════════════════════════════════════"
echo ""
"""


def _read_platform_public_key() -> str:
    """Read the platform's ansible public key from disk."""
    key_path = os.environ.get("SSH_KEY_PATH", "./keys/ansible_id_rsa")
    pub_key_path = key_path if key_path.endswith(".pub") else key_path + ".pub"
    if not os.path.isabs(pub_key_path):
        pub_key_path = os.path.join("/app", pub_key_path.lstrip("./"))

    try:
        with open(pub_key_path) as f:
            return f.read().strip()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Platform SSH key not yet generated. Start the backend container first.",
        )
