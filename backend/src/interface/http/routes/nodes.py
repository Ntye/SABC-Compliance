from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
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


# ── Dependency injection (set by main.py) ─────────────────────────────────────

_register_uc = None
_get_uc = None
_list_uc = None
_ping_uc = None
_ping_all_uc = None
_update_uc = None
_delete_uc = None


def set_use_cases(register_uc, get_uc, list_uc, ping_uc, ping_all_uc, update_uc, delete_uc) -> None:
    global _register_uc, _get_uc, _list_uc, _ping_uc, _ping_all_uc, _update_uc, _delete_uc
    _register_uc = register_uc
    _get_uc = get_uc
    _list_uc = list_uc
    _ping_uc = ping_uc
    _ping_all_uc = ping_all_uc
    _update_uc = update_uc
    _delete_uc = delete_uc


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
    Returns 422 if SSH fails.
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
    """Test SSH connectivity for every registered node concurrently."""
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
    """Test SSH connectivity for one node and update its status."""
    try:
        return await _ping_uc.execute(id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
