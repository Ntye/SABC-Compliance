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


# ── Dependency injection (set by main.py) ─────────────────────────────────────

_register_uc = None
_get_uc = None
_list_uc = None
_ping_uc = None
_ping_all_uc = None
_update_uc = None
_delete_uc = None
_check_dns_uc = None


def set_use_cases(
    register_uc, get_uc, list_uc, ping_uc, ping_all_uc,
    update_uc, delete_uc, check_dns_uc,
) -> None:
    global _register_uc, _get_uc, _list_uc, _ping_uc, _ping_all_uc
    global _update_uc, _delete_uc, _check_dns_uc
    _register_uc = register_uc
    _get_uc = get_uc
    _list_uc = list_uc
    _ping_uc = ping_uc
    _ping_all_uc = ping_all_uc
    _update_uc = update_uc
    _delete_uc = delete_uc
    _check_dns_uc = check_dns_uc


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


@router.get("/host-info", summary="Return platform host IP and hostname")
async def get_host_info(
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """
    Returns the IP address and hostname of the machine running the platform.
    Used by the Add VM page to pre-fill the form when registering the host itself.
    Set HOST_IP in .env for a reliable value; otherwise it is auto-detected.
    """
    host_ip = _detect_host_ip()
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = None
    return {"host_ip": host_ip, "hostname": hostname}


# ── Setup script ──────────────────────────────────────────────────────────────

_SETUP_SCRIPT_TEMPLATE = r"""#!/usr/bin/env bash
# BdC Compliance Platform — Node Bootstrap Script
#
# Usage (from backend/ directory):
#   bash setup-node.sh <server-ip> [admin-user]
#
#   server-ip    IP address or hostname of the target server
#   admin-user   SSH user with root or passwordless-sudo access (default: root)
#
# What this script does in a single SSH session:
#   1. Clears any stale host-key entry so known_hosts stays clean
#   2. Creates the 'ansible' OS user with a locked password
#   3. Installs the platform's public key for passwordless SSH
#   4. Grants the ansible user full passwordless sudo
#   5. Verifies the connection using the platform's private key
#
# You will be prompted for the admin user's SSH password once.
# Everything else is automated.
#
# Requirements:
#   - admin-user must be root OR have passwordless sudo (NOPASSWD:ALL).
#     If sudo requires a password, re-run with 'root' as the admin user.
#   - The script auto-locates the platform private key from its own directory.

set -euo pipefail

SERVER_IP="${1:-}"
ADMIN_USER="${2:-root}"

if [[ -z "$SERVER_IP" ]]; then
  echo "Usage: bash setup-node.sh <server-ip> [admin-user]"
  echo "  server-ip    IP or hostname of the target server"
  echo "  admin-user   SSH user with root/passwordless-sudo (default: root)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY_PRIV="${SCRIPT_DIR}/keys/ansible_id_rsa"

# Platform public key — embedded by the platform at download time
PLATFORM_KEY="__PLATFORM_PUBLIC_KEY__"
SSH_USER="ansible"

echo ""
echo "══════════════════════════════════════════════════════"
echo "  BdC Compliance — Node Bootstrap"
echo "  Target    : ${SERVER_IP}"
echo "  Admin user: ${ADMIN_USER}"
echo "══════════════════════════════════════════════════════"
echo ""

# ── 1. Clear stale host-key entries ──────────────────────────────────────────
echo "[1/3] Clearing stale host-key entries for ${SERVER_IP} ..."
ssh-keygen -R "${SERVER_IP}" 2>/dev/null || true

# ── 2. Bootstrap in one SSH session ──────────────────────────────────────────
echo "[2/3] Connecting as ${ADMIN_USER}@${SERVER_IP} — enter SSH password when prompted ..."
echo ""

# For non-root admin users all remote commands run via 'sudo bash'.
# This requires NOPASSWD sudo. If sudo needs a password, pass 'root' instead.
if [[ "$ADMIN_USER" == "root" ]]; then
  REMOTE_SHELL="bash -s"
else
  REMOTE_SHELL="sudo bash -s"
fi

ssh \
  -o StrictHostKeyChecking=no \
  -o ConnectTimeout=15 \
  "${ADMIN_USER}@${SERVER_IP}" \
  "$REMOTE_SHELL" << REMOTE
set -e

echo "  Creating ${SSH_USER} user ..."
useradd -m -s /bin/bash "${SSH_USER}" 2>/dev/null || true

echo "  Setting up .ssh directory ..."
mkdir -p /home/"${SSH_USER}"/.ssh
chmod 700 /home/"${SSH_USER}"/.ssh
chown "${SSH_USER}":"${SSH_USER}" /home/"${SSH_USER}"/.ssh

echo "  Installing platform public key ..."
if ! grep -qF "${PLATFORM_KEY}" /home/"${SSH_USER}"/.ssh/authorized_keys 2>/dev/null; then
  echo "${PLATFORM_KEY}" >> /home/"${SSH_USER}"/.ssh/authorized_keys
fi
chmod 600 /home/"${SSH_USER}"/.ssh/authorized_keys
chown "${SSH_USER}":"${SSH_USER}" /home/"${SSH_USER}"/.ssh/authorized_keys

echo "  Granting passwordless sudo ..."
echo "${SSH_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/"${SSH_USER}"
chmod 440 /etc/sudoers.d/"${SSH_USER}"

echo ""
echo "  Bootstrap complete on \$(hostname -f 2>/dev/null || hostname)."
REMOTE

# ── 3. Verify the platform key ────────────────────────────────────────────────
echo ""
echo "[3/3] Verifying platform key (no password should be prompted) ..."
echo ""

if ssh \
  -i "${KEY_PRIV}" \
  -o StrictHostKeyChecking=no \
  -o ConnectTimeout=5 \
  -o BatchMode=yes \
  "${SSH_USER}@${SERVER_IP}" \
  "echo '  SSH   : OK' && sudo id | sed 's/^/  sudo  : /'"; then
  echo ""
  echo "══════════════════════════════════════════════════════"
  echo "  ✓  ${SERVER_IP} is ready."
  echo "     Register it now in the Node Registry."
  echo "══════════════════════════════════════════════════════"
else
  echo ""
  echo "ERROR: Could not connect as ${SSH_USER}@${SERVER_IP} using the platform key."
  echo "Check that setup completed without errors above."
  exit 1
fi
"""


@router.get(
    "/setup-script",
    summary="Download the node bootstrap script",
    response_class=PlainTextResponse,
)
async def get_setup_script(
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """
    Returns a ready-to-run bash script that bootstraps SSH access on a new node.
    The platform's ansible public key is embedded in the script at download time.

    Run it from the backend/ directory:
        bash setup-node.sh <server-ip> [admin-user]
    """
    key_path = os.environ.get("SSH_KEY_PATH", "./keys/ansible_id_rsa")
    pub_key_path = key_path if key_path.endswith(".pub") else key_path + ".pub"
    if not os.path.isabs(pub_key_path):
        pub_key_path = os.path.join("/app", pub_key_path.lstrip("./"))

    try:
        with open(pub_key_path) as f:
            platform_key = f.read().strip()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Platform SSH key not yet generated. Start the backend container first.",
        )

    script = _SETUP_SCRIPT_TEMPLATE.replace("__PLATFORM_PUBLIC_KEY__", platform_key)

    return PlainTextResponse(
        content=script,
        headers={"Content-Disposition": 'attachment; filename="setup-node.sh"'},
        media_type="text/x-sh; charset=utf-8",
    )
