"""
Platform notifications — the header bell.

Written by background chains (an enforcement job launched from the Tiers page
finishing, its follow-up compliance scan completing) so the outcome reaches
operators who weren't watching the live job stream. Any authenticated
principal can read and acknowledge them; they are platform-wide, not per-user.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.domain.interfaces import INotificationRepository
from interface.http.routes.auth import get_current_principal

router = APIRouter(prefix="/notifications", tags=["Notifications"])

_repo: INotificationRepository | None = None


def set_repo(repo: INotificationRepository) -> None:
    global _repo
    _repo = repo


class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str | None = None
    kind: str = "info"
    severity: str = "info"
    node_id: str | None = None
    job_id: str | None = None
    is_read: bool = False
    created_at: datetime


def _resp(n) -> NotificationResponse:
    return NotificationResponse(
        id=n.id, title=n.title, message=n.message, kind=n.kind,
        severity=n.severity, node_id=n.node_id, job_id=n.job_id,
        is_read=n.is_read, created_at=n.created_at,
    )


@router.get("", response_model=list[NotificationResponse],
            summary="List platform notifications (newest first)")
async def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    if _repo is None:
        return []
    return [_resp(n) for n in await _repo.find_all(limit=limit, unread_only=unread_only)]


@router.get("/unread-count", summary="Number of unread notifications")
async def unread_count(principal: AuthPrincipal = Depends(get_current_principal)):
    if _repo is None:
        return {"count": 0}
    return {"count": await _repo.unread_count()}


@router.post("/{notification_id}/read", summary="Mark one notification as read")
async def mark_read(notification_id: str,
                    principal: AuthPrincipal = Depends(get_current_principal)):
    if _repo is None:
        raise HTTPException(status_code=503, detail="Notifications not available")
    if not await _repo.mark_read(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"read": True}


@router.post("/read-all", summary="Mark every notification as read")
async def mark_all_read(principal: AuthPrincipal = Depends(get_current_principal)):
    if _repo is None:
        raise HTTPException(status_code=503, detail="Notifications not available")
    return {"read": await _repo.mark_all_read()}
