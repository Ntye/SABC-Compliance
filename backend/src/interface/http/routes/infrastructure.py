from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.errors import NotFoundError, ValidationError
from interface.http.routes.auth import get_current_principal, require_operator

router = APIRouter(prefix="/infrastructure", tags=["Infrastructure"])

# ── Pydantic models ───────────────────────────────────────────────────────────

class ServiceStatus(BaseModel):
    configured: bool
    host: str | None = None
    port: int
    reachable: bool | None = None


class InfrastructureStatusResponse(BaseModel):
    puppet: ServiceStatus
    wazuh: ServiceStatus


class SetHostRequest(BaseModel):
    host: str


class InstallRequest(BaseModel):
    node_id: str


class JobRef(BaseModel):
    id: str
    type: str
    status: str
    node_id: str | None = None


# ── Dependency injection ──────────────────────────────────────────────────────

_get_status_uc = None
_set_master_uc = None
_install_puppet_master_uc = None
_install_wazuh_manager_uc = None
_install_puppet_agent_uc = None
_install_wazuh_agent_uc = None


def set_use_cases(
    get_status_uc,
    set_master_uc,
    install_puppet_master_uc,
    install_wazuh_manager_uc,
    install_puppet_agent_uc,
    install_wazuh_agent_uc,
) -> None:
    global _get_status_uc, _set_master_uc
    global _install_puppet_master_uc, _install_wazuh_manager_uc
    global _install_puppet_agent_uc, _install_wazuh_agent_uc
    _get_status_uc = get_status_uc
    _set_master_uc = set_master_uc
    _install_puppet_master_uc = install_puppet_master_uc
    _install_wazuh_manager_uc = install_wazuh_manager_uc
    _install_puppet_agent_uc = install_puppet_agent_uc
    _install_wazuh_agent_uc = install_wazuh_agent_uc


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/status", response_model=InfrastructureStatusResponse, summary="Get infrastructure status")
async def get_status(principal: AuthPrincipal = Depends(get_current_principal)):
    """Returns connectivity status for Puppet master and Wazuh manager."""
    result = await _get_status_uc.execute()
    return InfrastructureStatusResponse(
        puppet=ServiceStatus(**result["puppet"]),
        wazuh=ServiceStatus(**result["wazuh"]),
    )


@router.post("/puppet-master", summary="Connect to an existing Puppet master")
async def set_puppet_master(
    body: SetHostRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Save a Puppet master hostname and test connectivity."""
    try:
        return await _set_master_uc.execute("puppet", body.host)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/wazuh-manager", summary="Connect to an existing Wazuh manager")
async def set_wazuh_manager(
    body: SetHostRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Save a Wazuh manager hostname and test connectivity."""
    try:
        return await _set_master_uc.execute("wazuh", body.host)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/install/puppet-master", response_model=JobRef, status_code=202, summary="Install Puppet master on a node")
async def install_puppet_master(
    body: InstallRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Start an Ansible job to install Puppet master on the specified node."""
    try:
        job = await _install_puppet_master_uc.execute(body.node_id)
        return JobRef(id=job.id, type=job.type, status=job.status, node_id=job.node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/install/wazuh-manager", response_model=JobRef, status_code=202, summary="Install Wazuh manager on a node")
async def install_wazuh_manager(
    body: InstallRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Start an Ansible job to install Wazuh manager on the specified node."""
    try:
        job = await _install_wazuh_manager_uc.execute(body.node_id)
        return JobRef(id=job.id, type=job.type, status=job.status, node_id=job.node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/install/puppet-agent", response_model=JobRef, status_code=202, summary="Install Puppet agent on a node")
async def install_puppet_agent(
    body: InstallRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Start an Ansible job to install and enroll the Puppet agent on the specified node."""
    try:
        job = await _install_puppet_agent_uc.execute(body.node_id)
        return JobRef(id=job.id, type=job.type, status=job.status, node_id=job.node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/install/wazuh-agent", response_model=JobRef, status_code=202, summary="Install Wazuh agent on a node")
async def install_wazuh_agent(
    body: InstallRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Start an Ansible job to install and enroll the Wazuh agent on the specified node."""
    try:
        job = await _install_wazuh_agent_uc.execute(body.node_id)
        return JobRef(id=job.id, type=job.type, status=job.status, node_id=job.node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
