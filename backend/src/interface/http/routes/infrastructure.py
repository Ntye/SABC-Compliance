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


class SetPuppetCredentialsRequest(BaseModel):
    admin_user: str = "admin"
    admin_password: str


class InstallRequest(BaseModel):
    node_id: str


class WazuhInstallRequest(InstallRequest):
    dashboard_port: int | None = None


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
_install_wazuh_manager_colocated_uc = None
_configure_wazuh_remediation_uc = None
_install_puppet_agent_uc = None
_install_wazuh_agent_uc = None
_check_health_uc = None
_scan_engine_uc = None
_node_repo = None
_packages_dir: str = ""
_ssh_client = None
_config_repo = None


def set_use_cases(
    get_status_uc,
    set_master_uc,
    install_puppet_master_uc,
    install_wazuh_manager_uc,
    install_puppet_agent_uc,
    install_wazuh_agent_uc,
    check_health_uc=None,
    scan_engine_uc=None,
    node_repo=None,
    packages_dir: str = "",
    install_wazuh_manager_colocated_uc=None,
    ssh_client=None,
    config_repo=None,
    configure_wazuh_remediation_uc=None,
) -> None:
    global _get_status_uc, _set_master_uc
    global _install_puppet_master_uc, _install_wazuh_manager_uc
    global _install_wazuh_manager_colocated_uc, _configure_wazuh_remediation_uc
    global _install_puppet_agent_uc, _install_wazuh_agent_uc
    global _check_health_uc, _scan_engine_uc
    global _node_repo, _packages_dir, _ssh_client, _config_repo
    _get_status_uc = get_status_uc
    _set_master_uc = set_master_uc
    _install_puppet_master_uc = install_puppet_master_uc
    _install_wazuh_manager_uc = install_wazuh_manager_uc
    _install_wazuh_manager_colocated_uc = install_wazuh_manager_colocated_uc
    _configure_wazuh_remediation_uc = configure_wazuh_remediation_uc
    _install_puppet_agent_uc = install_puppet_agent_uc
    _install_wazuh_agent_uc = install_wazuh_agent_uc
    _check_health_uc = check_health_uc
    _scan_engine_uc = scan_engine_uc
    _node_repo = node_repo
    _packages_dir = packages_dir
    _ssh_client = ssh_client
    _config_repo = config_repo


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


@router.post("/puppet-credentials", summary="Set Puppet Enterprise RBAC credentials")
async def set_puppet_credentials(
    body: SetPuppetCredentialsRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Store the PE console admin username and password used by SABC to
    authenticate against the RBAC API for node-group classification.

    Call this whenever the PE console admin password changes — the stored
    credentials are used by every subsequent node-group sync.
    """
    if not _config_repo:
        raise HTTPException(status_code=503, detail="Config repository not available")
    password = body.admin_password.strip()
    if not password:
        raise HTTPException(status_code=422, detail="admin_password is required")
    await _config_repo.set("pe_console_password", password)
    await _config_repo.set("pe_admin_user", body.admin_user.strip() or "admin")
    return {"message": "Puppet Enterprise credentials updated", "admin_user": body.admin_user}


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


@router.get("/probe-dashboard-port", summary="Find the first available dashboard port on a node")
async def probe_dashboard_port(
    node_id: str = Query(...),
    principal: AuthPrincipal = Depends(require_operator),
):
    """
    SSH to the node, list listening ports, and return the first free port
    from the candidate list [443, 8443, 8444, 9443, 10443].
    Always returns a result — never raises if SSH fails.
    """
    if _node_repo is None or _ssh_client is None:
        return {"suggested_port": 443, "occupied_ports": [], "occupied_candidates": []}

    node = await _node_repo.find_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    used_ports: set[int] = set()
    try:
        stdout, _, _ = await _ssh_client.run_command(
            node.ip,
            node.ssh_port,
            node.ssh_user,
            node.ssh_key_path,
            "ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' | grep -oE '[0-9]+$' | sort -nu || true"
        )
        for line in (stdout or "").splitlines():
            line = line.strip()
            if line.isdigit():
                used_ports.add(int(line))
    except Exception:
        pass  # SSH unreachable — return defaults

    candidates = [443, 8443, 8444, 9443, 10443]
    suggested = next((p for p in candidates if p not in used_ports), 8443)
    occupied_candidates = [p for p in candidates if p in used_ports]

    return {
        "suggested_port": suggested,
        "occupied_ports": sorted(used_ports),
        "occupied_candidates": occupied_candidates,
    }


@router.post("/install/wazuh-manager", response_model=JobRef, status_code=202, summary="Install Wazuh manager on a node")
async def install_wazuh_manager(
    body: WazuhInstallRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Start an Ansible job to install Wazuh manager on the specified node."""
    try:
        job = await _install_wazuh_manager_uc.execute(body.node_id, dashboard_port=body.dashboard_port)
        return JobRef(id=job.id, type=job.type, status=job.status, node_id=job.node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/install/wazuh-manager-colocated", response_model=JobRef, status_code=202, summary="Install Wazuh manager alongside an existing Puppet Primary Server")
async def install_wazuh_manager_colocated(
    body: WazuhInstallRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Start a Puppet-safe Ansible job to install Wazuh on a node that already
    runs Puppet Server or Puppet Enterprise.  The job verifies Puppet health
    before and after installation and automatically resolves port conflicts
    (e.g. Puppet Enterprise :443 vs Wazuh dashboard :443).
    """
    if _install_wazuh_manager_colocated_uc is None:
        raise HTTPException(status_code=503, detail="Colocated Wazuh install use case not configured")
    try:
        job = await _install_wazuh_manager_colocated_uc.execute(body.node_id, dashboard_port=body.dashboard_port)
        return JobRef(id=job.id, type=job.type, status=job.status, node_id=job.node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/configure/wazuh-remediation", response_model=JobRef, status_code=202, summary="Wire the Wazuh→Puppet closed remediation loop on the manager node")
async def configure_wazuh_remediation(
    body: InstallRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Install the `custom-sabc` integration on the Wazuh manager so it forwards
    alerts to the platform webhook, closing the detection → remediation loop.

    Derives the webhook URL from PLATFORM_PUBLIC_HOST/HTTPS_PORT and the shared
    secret from the platform's wazuh_webhook_secret — both must be configured.
    """
    if _configure_wazuh_remediation_uc is None:
        raise HTTPException(status_code=503, detail="Remediation configuration use case not configured")
    try:
        job = await _configure_wazuh_remediation_uc.execute(body.node_id)
        return JobRef(id=job.id, type=job.type, status=job.status, node_id=job.node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


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


@router.post("/check-health", response_model=JobRef, status_code=202, summary="Run a read-only node health check")
async def check_node_health(
    body: InstallRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Start a read-only Ansible diagnostic job that reports Puppet/Wazuh/network state."""
    if _check_health_uc is None:
        raise HTTPException(status_code=503, detail="Health check use case not configured")
    try:
        job = await _check_health_uc.execute(body.node_id)
        return JobRef(id=job.id, type=job.type, status=job.status, node_id=job.node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Scan engine (platform controller) ─────────────────────────────────────────
# The scan engine (CINC Auditor) is agentless: it lives on the SABC platform
# and reaches each node over SSH. These endpoints expose the controller-side
# install state and let the operator verify that the platform can probe each node.

class ScanEngineStatusResponse(BaseModel):
    installed: bool
    version: str | None = None
    executable_path: str


class ScanEngineVerifyResult(BaseModel):
    node_id: str | None = None
    hostname: str | None = None
    reachable: bool
    output: str | None = None
    error: str | None = None


class ScanEngineVerifyAllResponse(BaseModel):
    controller: ScanEngineStatusResponse
    total: int = 0
    reachable: int = 0
    results: list[ScanEngineVerifyResult] = []
    error: str | None = None


@router.get("/scan-engine/status", response_model=ScanEngineStatusResponse, summary="Scan engine platform install status")
async def get_scan_engine_status(principal: AuthPrincipal = Depends(get_current_principal)):
    """Return whether the scan engine (CINC Auditor) is installed on the SABC platform server."""
    if _scan_engine_uc is None:
        raise HTTPException(status_code=503, detail="Scan engine use case not configured")
    return ScanEngineStatusResponse(**(await _scan_engine_uc.get_status()))


@router.post("/scan-engine/install", summary="Install the scan engine on the platform server")
async def install_scan_engine_on_controller(principal: AuthPrincipal = Depends(require_operator)):
    """Run the CINC Auditor installer inside the platform container."""
    if _scan_engine_uc is None:
        raise HTTPException(status_code=503, detail="Scan engine use case not configured")
    result = await _scan_engine_uc.install_on_controller()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result)
    return result


@router.post("/scan-engine/verify", response_model=ScanEngineVerifyAllResponse, summary="Verify scan engine can reach every node")
async def verify_scan_engine_all(principal: AuthPrincipal = Depends(require_operator)):
    """Probe every node over SSH and mark nodes scan_ready when reachable."""
    if _scan_engine_uc is None:
        raise HTTPException(status_code=503, detail="Scan engine use case not configured")
    return await _scan_engine_uc.verify_all_nodes()


@router.post("/scan-engine/verify/{node_id}", response_model=ScanEngineVerifyResult, summary="Verify scan engine can reach a single node")
async def verify_scan_engine_node(node_id: str, principal: AuthPrincipal = Depends(require_operator)):
    """Probe one node and update its scan_ready flag."""
    if _scan_engine_uc is None:
        raise HTTPException(status_code=503, detail="Scan engine use case not configured")
    try:
        return await _scan_engine_uc.verify_node(node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
