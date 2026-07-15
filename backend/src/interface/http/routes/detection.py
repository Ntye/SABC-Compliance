"""
Operator-facing detection endpoints (standard API-key / JWT auth).

The agent-facing ingest endpoint lives in webhooks.py (shared-key auth);
these routes serve the dashboard: the Detection Events page and the
watched-paths / agent-liveness panel on the node detail page.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.errors import NotFoundError
from interface.http.routes.auth import get_current_principal, require_admin, require_operator
from core.errors import ValidationError

router = APIRouter(prefix="/detection", tags=["Detection"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class DetectionEventResponse(BaseModel):
    id: str
    node_id: str
    hostname: str
    path: str
    event_type: str
    timestamp: datetime
    prev_hash: str | None = None
    new_hash: str | None = None
    file_meta: dict | None = None
    puppet_running: bool = False
    actor: dict | None = None
    suppressed: bool = False
    suppress_reason: str | None = None
    remediation_event_id: str | None = None
    remediation_outcome: str | None = None
    violation: bool | None = None            # None=unassessed, False=benign, True=alert
    violation_detail: str | None = None
    created_at: datetime


class WatchedPathStatus(BaseModel):
    path: str
    last_event_type: str
    last_event_at: datetime
    last_hash: str | None = None
    suppressed: bool = False
    events: int = 0


class NodeDetectionStatusResponse(BaseModel):
    node_id: str
    hostname: str
    detection_enrolled: bool
    agent_last_seen: datetime | None = None
    watched_paths: list[WatchedPathStatus] = []
    recent_events: int = 0


class ConfigBlobResponse(BaseModel):
    sha256: str
    size: int
    first_seen_at: str | None = None
    text: str = ""
    is_binary: bool = False
    truncated: bool = False


class WatchConfigResponse(BaseModel):
    paths: list[str]
    hash_only: list[str] = []
    is_default: bool = False


class WatchConfigRequest(BaseModel):
    paths: list[str]
    hash_only: list[str] = []


# ── Dependency injection (set by main.py) ─────────────────────────────────────

_list_events_uc = None
_node_status_uc = None
_blob_uc = None
_get_watch_uc = None
_update_watch_uc = None
_apply_watch_uc = None


def set_use_cases(list_events_uc=None, node_status_uc=None, blob_uc=None,
                  get_watch_uc=None, update_watch_uc=None, apply_watch_uc=None) -> None:
    global _list_events_uc, _node_status_uc, _blob_uc
    global _get_watch_uc, _update_watch_uc, _apply_watch_uc
    _list_events_uc = list_events_uc
    _node_status_uc = node_status_uc
    _blob_uc = blob_uc
    _get_watch_uc = get_watch_uc
    _update_watch_uc = update_watch_uc
    _apply_watch_uc = apply_watch_uc


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/events", response_model=list[DetectionEventResponse],
            summary="List config-change events reported by the detection agents")
async def list_detection_events(
    node_id: str | None = Query(None, description="Filter by node id"),
    limit: int = Query(100, ge=1, le=500),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """Newest-first evidence trail from the detection plane. Suppressed events
    (active remediation window, scheduled Puppet run, baselines) are included —
    the `suppressed` flag and `suppress_reason` say why nothing was triggered."""
    if _list_events_uc is None:
        raise HTTPException(status_code=503, detail="Detection module not initialised")
    return await _list_events_uc.execute(node_id=node_id, limit=limit)


@router.get("/nodes/{id}/status", response_model=NodeDetectionStatusResponse,
            summary="Detection agent status for one node")
async def get_node_detection_status(
    id: str,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """Agent liveness (`agent_last_seen`, derived from the most recent event or
    heartbeat) and the per-path watch status shown on the node detail page."""
    if _node_status_uc is None:
        raise HTTPException(status_code=503, detail="Detection module not initialised")
    try:
        return await _node_status_uc.execute(id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/blobs/{sha256}", response_model=ConfigBlobResponse,
            summary="Fetch a content-addressed file snapshot (for the diff view)")
async def get_config_blob(
    sha256: str,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """Return the stored snapshot for a hash. The detection remediation view is
    a diff of the previous snapshot (`prev_hash`) against the new one
    (`new_hash`); the modal fetches both blobs here. Text is decoded best-effort
    and capped — `is_binary` / `truncated` flag anything the diff can't show."""
    if _blob_uc is None:
        raise HTTPException(status_code=503, detail="Detection module not initialised")
    try:
        return await _blob_uc.execute(sha256)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Watch configuration (folders/files monitored by the agents) ───────────────

@router.get("/watch-config", response_model=WatchConfigResponse,
            summary="Get the folders/files the detection agents monitor")
async def get_watch_config(principal: AuthPrincipal = Depends(get_current_principal)):
    """The platform-managed watch list applied to detection agents (falls back
    to the built-in default set when the operator hasn't customised it)."""
    if _get_watch_uc is None:
        raise HTTPException(status_code=503, detail="Detection module not initialised")
    return await _get_watch_uc.execute()


@router.put("/watch-config", response_model=WatchConfigResponse,
            summary="Update the monitored folders/files (operator)")
async def update_watch_config(body: WatchConfigRequest,
                              principal: AuthPrincipal = Depends(require_operator)):
    """Set the folders/files the agents monitor. Takes effect on newly enrolled
    agents immediately; use /watch-config/apply to push it to existing nodes."""
    if _update_watch_uc is None:
        raise HTTPException(status_code=503, detail="Detection module not initialised")
    try:
        return await _update_watch_uc.execute(
            {"paths": body.paths, "hash_only": body.hash_only},
            actor=getattr(principal, "name", None),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/watch-config/apply",
             summary="Push the current watch config to enrolled nodes (operator)")
async def apply_watch_config(node_id: str | None = Query(None),
                             principal: AuthPrincipal = Depends(require_operator)):
    """Re-run the (idempotent) agent install on every detection-enrolled node —
    or one node — so it picks up the current watch config and restarts. Returns
    the launched job(s)."""
    if _apply_watch_uc is None:
        raise HTTPException(status_code=503, detail="Detection module not initialised")
    return await _apply_watch_uc.execute(node_id=node_id, actor=getattr(principal, "name", None))
