from __future__ import annotations
import glob
import os
from fastapi import APIRouter, Depends, HTTPException, Query
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
_install_inspec_uc = None
_node_repo = None
_packages_dir: str = ""


def set_use_cases(
    get_status_uc,
    set_master_uc,
    install_puppet_master_uc,
    install_wazuh_manager_uc,
    install_puppet_agent_uc,
    install_wazuh_agent_uc,
    install_inspec_uc=None,
    node_repo=None,
    packages_dir: str = "",
) -> None:
    global _get_status_uc, _set_master_uc
    global _install_puppet_master_uc, _install_wazuh_manager_uc
    global _install_puppet_agent_uc, _install_wazuh_agent_uc
    global _install_inspec_uc
    global _node_repo, _packages_dir
    _get_status_uc = get_status_uc
    _set_master_uc = set_master_uc
    _install_puppet_master_uc = install_puppet_master_uc
    _install_wazuh_manager_uc = install_wazuh_manager_uc
    _install_puppet_agent_uc = install_puppet_agent_uc
    _install_wazuh_agent_uc = install_wazuh_agent_uc
    _install_inspec_uc = install_inspec_uc
    _node_repo = node_repo
    _packages_dir = packages_dir


def _puppet_agent_platform(os_family: str | None, os_name: str | None, os_version: str | None) -> str:
    """Build the PE platform string from node OS facts."""
    if os_family == "Debian":
        name = (os_name or "").lower()
        version = os_version or ""
        return f"{name}-{version}-amd64"
    else:
        major = (os_version or "").split(".")[0]
        return f"el-{major}-x86_64"


# ── Routes ────────────────────────────────────────────────────────────────────

class PlatformCheckResponse(BaseModel):
    platform: str
    has_tarball: bool
    tarball_name: str
    packages_dir: str


@router.get("/puppet-agent/platform-check", response_model=PlatformCheckResponse, summary="Check platform package availability")
async def puppet_agent_platform_check(
    node_id: str = Query(...),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """Check whether a platform tarball is available for the node's OS."""
    if _node_repo is None:
        raise HTTPException(status_code=503, detail="Node repository not available")
    try:
        node = await _node_repo.get(node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    platform = _puppet_agent_platform(node.os_family, node.os_name, node.os_version)
    tarball_name = f"puppet-agent-{platform}.tar.gz"
    agent_pkg_dir = os.path.join(_packages_dir, "puppet-agent")
    pattern = os.path.join(agent_pkg_dir, tarball_name)
    has_tarball = bool(glob.glob(pattern))

    return PlatformCheckResponse(
        platform=platform,
        has_tarball=has_tarball,
        tarball_name=tarball_name,
        packages_dir=agent_pkg_dir,
    )


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


@router.post("/install/inspec", response_model=JobRef, status_code=202, summary="Install InSpec on a node")
async def install_inspec(
    body: InstallRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Start an Ansible job to install the Chef InSpec scanner on the specified node."""
    if _install_inspec_uc is None:
        raise HTTPException(status_code=503, detail="InSpec install use case not configured")
    try:
        job = await _install_inspec_uc.execute(body.node_id)
        return JobRef(id=job.id, type=job.type, status=job.status, node_id=job.node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
