from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.domain.entities import AuthPrincipal
from core.errors import NotFoundError, ValidationError
from interface.http.routes.auth import get_current_principal, require_operator, require_admin
from modules.compliance.scheduler import UNITS_TO_SECONDS
from modules.detection.usecases import DETECTION_CLOSED_LOOP_CONFIG_KEY

router = APIRouter(prefix="/compliance", tags=["Compliance"])

# ── Pydantic models ───────────────────────────────────────────────────────────

class CollectRequest(BaseModel):
    profile_id: str | None = None  # None/"all" → default; "cis-benchmark" or "sabc-linux-baseline"

class RemediateRequest(BaseModel):
    description: str | None = None

class ClosedLoopRequest(BaseModel):
    # Exactly one of node_id / group_id. Enforce (Puppet) → re-scan (CINC) for a
    # single node or every member of a node group.
    node_id: str | None = None
    group_id: str | None = None
    description: str | None = None
    rescan: bool = True

class ScanScheduleRequest(BaseModel):
    enabled: bool = True
    interval: int = Field(default=30, ge=1)
    unit: str = "minutes"  # "seconds" | "minutes" | "days"

class ClosedLoopSettingRequest(BaseModel):
    enabled: bool = False

class EnforceRequest(BaseModel):
    # Exactly one of node_id / group_id. Apply the tier-applicable referential
    # (sabc_hardening) so the internal referential fully passes on the target.
    node_id: str | None = None
    group_id: str | None = None


# ── Dependency injection (set by main.py) ─────────────────────────────────────

_summary_uc = None
_node_uc = None
_collect_uc = None
_remediate_uc = None
_closed_loop_uc = None
_enforce_uc = None
_config_repo = None


def set_use_cases(summary_uc, node_uc, collect_uc, remediate_uc, config_repo=None,
                  closed_loop_uc=None, enforce_uc=None) -> None:
    global _summary_uc, _node_uc, _collect_uc, _remediate_uc, _config_repo
    global _closed_loop_uc, _enforce_uc
    _summary_uc = summary_uc
    _node_uc = node_uc
    _collect_uc = collect_uc
    _remediate_uc = remediate_uc
    _closed_loop_uc = closed_loop_uc
    _enforce_uc = enforce_uc
    _config_repo = config_repo


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/summary", summary="Fleet-wide compliance overview")
async def compliance_summary(principal: AuthPrincipal = Depends(get_current_principal)):
    """One row per node with its latest compliance reports and remediation events."""
    return await _summary_uc.execute()


@router.get("/nodes/{id}", summary="Compliance detail for a single node")
async def node_compliance(id: str, principal: AuthPrincipal = Depends(get_current_principal)):
    """Reports (with per-control detail) and remediation history for a node."""
    try:
        return await _node_uc.execute(id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/nodes/{id}/collect", summary="Run a compliance scan on an enrolled node")
async def collect_node_compliance(
    id: str,
    body: Optional[CollectRequest] = None,
    principal: AuthPrincipal = Depends(require_operator),
):
    """
    Run a structured compliance scan (bundled CIS-aligned profile) against the node
    over SSH from the controller, and read the Puppet last-run summary when the
    Puppet agent is enrolled. Results are stored as compliance reports. There is no
    shell fallback — a complete scan or a clear, actionable error.

    Optional body: ``{"profile_id": "cis-benchmark" | "sabc-linux-baseline"}``
    to label the stored report with a specific compliance profile.
    Omit (or pass ``null``) to use the default profile from the scan output.
    """
    profile_id = body.profile_id if body else None
    try:
        return await _collect_uc.execute(id, profile_id=profile_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/nodes/{id}/remediate", summary="Trigger remediation on a node")
async def remediate_node(id: str, body: RemediateRequest, principal: AuthPrincipal = Depends(require_operator)):
    """Run a Puppet enforcement pass over SSH and record the remediation event."""
    try:
        return await _remediate_uc.execute(id, body.description)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/closed-loop", summary="Run the closed remediation loop on a node or a node group")
async def run_closed_loop(
    body: ClosedLoopRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Enforce compliance with Puppet and re-scan, for a single node
    (``{"node_id": "..."}``) or every member of a node group
    (``{"group_id": "..."}``). Provide exactly one. Per-node progress is streamed
    over the node's WebSocket channel; the response returns the aggregate once
    the run completes.
    """
    if _closed_loop_uc is None:
        raise HTTPException(status_code=503, detail="Closed-loop remediation not available")
    try:
        return await _closed_loop_uc.execute(
            node_id=body.node_id,
            group_id=body.group_id,
            description=body.description,
            rescan=body.rescan,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/enforce", summary="Enforce the full referential on a node or a node group")
async def enforce_referential(
    body: EnforceRequest,
    principal: AuthPrincipal = Depends(require_operator),
):
    """Apply the generated ``sabc_hardening`` module — scoped to the target's
    tier- and family-applicable controls — so the internal referential fully
    passes. Provide exactly one of ``{"node_id": "..."}`` or
    ``{"group_id": "..."}`` (a Puppet node group; every member is enforced).

    Returns the launched Ansible job(s); each streams progress on its own job
    channel. Follow with a compliance scan to confirm the node now passes.
    """
    if _enforce_uc is None:
        raise HTTPException(status_code=503, detail="Referential enforcement not available")
    try:
        return await _enforce_uc.execute(node_id=body.node_id, group_id=body.group_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/schedule", summary="Get the auto-scan schedule")
async def get_scan_schedule(principal: AuthPrincipal = Depends(get_current_principal)):
    """Return the current auto-scan schedule and the estimated next-run timestamp."""
    if not _config_repo:
        return {"enabled": True, "interval": 30, "unit": "minutes", "last_run": None, "next_run": None}

    enabled_raw = (await _config_repo.get("auto_scan_enabled")) or "true"
    enabled = enabled_raw == "true"
    interval = int((await _config_repo.get("auto_scan_interval")) or "30")
    unit = (await _config_repo.get("auto_scan_unit")) or "minutes"
    last_run = await _config_repo.get("auto_scan_last_run")

    next_run: str | None = None
    if enabled and last_run:
        secs = interval * UNITS_TO_SECONDS.get(unit, 60)
        next_run = (datetime.fromisoformat(last_run) + timedelta(seconds=secs)).isoformat()

    return {
        "enabled": enabled,
        "interval": interval,
        "unit": unit,
        "last_run": last_run,
        "next_run": next_run,
    }


@router.put("/schedule", summary="Update the auto-scan schedule (admin only)")
async def update_scan_schedule(
    body: ScanScheduleRequest,
    principal: AuthPrincipal = Depends(require_admin),
):
    """Configure the automatic compliance scan schedule. Requires admin role."""
    if body.unit not in UNITS_TO_SECONDS:
        raise HTTPException(status_code=422, detail=f"unit must be one of: {', '.join(UNITS_TO_SECONDS)}")
    if not _config_repo:
        raise HTTPException(status_code=500, detail="Config repository not available")

    await _config_repo.set("auto_scan_enabled", "true" if body.enabled else "false")
    await _config_repo.set("auto_scan_interval", str(body.interval))
    await _config_repo.set("auto_scan_unit", body.unit)
    return {"ok": True, "enabled": body.enabled, "interval": body.interval, "unit": body.unit}


@router.get("/closed-loop/settings", summary="Get the global closed-loop enforcement setting")
async def get_closed_loop_setting(principal: AuthPrincipal = Depends(get_current_principal)):
    """Whether detection events auto-trigger Puppet remediation platform-wide.

    When off (the default), a detected change always launches a compliance
    scan but never enforces on its own; a node group's ``active_response`` can
    still enable the loop for its own members regardless of this switch."""
    if not _config_repo:
        return {"enabled": False}
    raw = await _config_repo.get(DETECTION_CLOSED_LOOP_CONFIG_KEY)
    return {"enabled": (raw or "").strip().lower() in {"true", "1", "yes", "on"}}


@router.put("/closed-loop/settings", summary="Enable/disable global closed-loop enforcement (admin only)")
async def update_closed_loop_setting(
    body: ClosedLoopSettingRequest,
    principal: AuthPrincipal = Depends(require_admin),
):
    """Flip the platform-wide closed loop. With it on, every genuine detected
    change enforces with Puppet after scanning; with it off, detection observes
    and scans only. Requires admin role."""
    if not _config_repo:
        raise HTTPException(status_code=500, detail="Config repository not available")
    await _config_repo.set(DETECTION_CLOSED_LOOP_CONFIG_KEY, "true" if body.enabled else "false")
    return {"ok": True, "enabled": body.enabled}
