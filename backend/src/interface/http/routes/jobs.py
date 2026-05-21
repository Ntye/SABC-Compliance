from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.errors import NotFoundError
from interface.http.routes.auth import get_current_principal, require_operator

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# ── Pydantic models ───────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    id: str
    type: str
    status: str
    node_id: str | None = None
    target_group: str | None = None
    playbook: str
    exit_code: int | None = None
    log_count: int = 0
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobDetailResponse(JobResponse):
    logs: list[dict] = []


# ── Dependency injection ──────────────────────────────────────────────────────

_list_uc = None
_get_uc = None
_cancel_uc = None
_ws_manager = None


def set_use_cases(list_uc, get_uc, cancel_uc, ws_manager) -> None:
    global _list_uc, _get_uc, _cancel_uc, _ws_manager
    _list_uc = list_uc
    _get_uc = get_uc
    _cancel_uc = cancel_uc
    _ws_manager = ws_manager


def _to_response(job) -> JobResponse:
    return JobResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        node_id=job.node_id,
        target_group=job.target_group,
        playbook=job.playbook,
        exit_code=job.exit_code,
        log_count=len(job.logs),
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _to_detail(job) -> JobDetailResponse:
    return JobDetailResponse(
        **_to_response(job).model_dump(),
        logs=job.logs,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[JobResponse], summary="List recent jobs")
async def list_jobs(
    limit: int = 50,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """Return the most recent jobs, newest first."""
    jobs = await _list_uc.execute(limit)
    return [_to_response(j) for j in jobs]


@router.get("/{job_id}", response_model=JobDetailResponse, summary="Get job with full logs")
async def get_job(job_id: str, principal: AuthPrincipal = Depends(get_current_principal)):
    """Retrieve a job by ID including all stored log lines."""
    try:
        job = await _get_uc.execute(job_id)
        return _to_detail(job)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{job_id}/cancel", response_model=JobResponse, summary="Cancel a running job")
async def cancel_job(job_id: str, principal: AuthPrincipal = Depends(require_operator)):
    """Send SIGTERM to the Ansible process and mark the job as cancelled."""
    try:
        job = await _cancel_uc.execute(job_id)
        return _to_response(job)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.websocket("/{job_id}/ws")
async def ws_job_logs(job_id: str, websocket: WebSocket):
    """
    WebSocket endpoint for real-time job log streaming.
    On connect: replays all stored log lines, then streams live lines.
    Each message is a JSON object: {ts, level, line}.
    """
    await _ws_manager.connect(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        _ws_manager.disconnect(job_id, websocket)
