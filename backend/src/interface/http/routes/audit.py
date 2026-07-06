"""Audit log — who did what, with a focus on data exports.

Two ways an entry lands in the ``audit_log`` table:

* The :class:`AuditMiddleware` writes a generic, attributable row for every
  request (method, path, status, and the resolved user).
* Routes can write a richer, explicit row via :func:`record_export` — used for
  every data export so the log answers "who exported what, in which format".
  Client-side exports (fleet / node CSV·JSON·PDF built in the browser) report
  themselves through ``POST /audit/exports``.

Reading the log is admin-only; recording an export requires operator rights
(the same bar as producing the export in the first place).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.domain.interfaces import IAuditRepository
from interface.http.routes.auth import get_current_principal, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit"])

# ── Dependency injection (set by main.py) ─────────────────────────────────────

_repo: IAuditRepository | None = None


def set_repo(repo: IAuditRepository) -> None:
    global _repo
    _repo = repo


def _get_repo(request: Request) -> IAuditRepository | None:
    return _repo or getattr(request.app.state, "audit_repo", None)


# ── Shared recording helper (used by this router and other routes) ────────────

def _export_entry(request: Request, principal: AuthPrincipal | None, *,
                  resource_type: str, resource_id: str | None,
                  resource_name: str | None, fmt: str | None,
                  count: int | None, detail: dict | None,
                  status_code: int = 200) -> dict:
    payload = dict(detail or {})
    if count is not None:
        payload.setdefault("count", count)
    api_key_name = None
    if principal is not None and getattr(principal, "source", None) == "api_key":
        api_key_name = f"{principal.id[:8]}..."
    return {
        "ts": datetime.utcnow().isoformat(),
        "method": request.method,
        "path": str(request.url.path),
        "status_code": status_code,
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "duration_ms": None,
        "api_key_name": api_key_name,
        "user_id": getattr(principal, "id", None),
        "user_name": getattr(principal, "name", None),
        "user_role": getattr(principal, "role", None),
        "action": "export",
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "format": (fmt or "").lower() or None,
        "detail": json.dumps(payload) if payload else None,
    }


async def record_export(request: Request, principal: AuthPrincipal | None, *,
                        resource_type: str, resource_id: str | None = None,
                        resource_name: str | None = None, fmt: str | None = None,
                        count: int | None = None, detail: dict | None = None) -> None:
    """Write an explicit 'export' audit row and mark the request as handled so
    the middleware does not also log a generic duplicate. Best-effort: a logging
    failure must never break the export itself."""
    repo = _get_repo(request)
    request.state.audit_handled = True
    if repo is None:
        return
    try:
        await repo.save(_export_entry(
            request, principal, resource_type=resource_type, resource_id=resource_id,
            resource_name=resource_name, fmt=fmt, count=count, detail=detail,
        ))
    except Exception:  # pragma: no cover - audit must never break the caller
        logger.warning("Failed to record export audit entry", exc_info=True)


# ── Request/response models ───────────────────────────────────────────────────

class ExportEventRequest(BaseModel):
    resource_type: str                     # "fleet" | "node" | "profile" | …
    format: str                            # "csv" | "json" | "pdf"
    resource_id: str | None = None
    resource_name: str | None = None
    count: int | None = None
    detail: dict | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/exports", status_code=201,
             summary="Record a data export in the audit log (who + what)")
async def record_export_event(
    body: ExportEventRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """Called by the frontend for browser-side exports so they are attributed to
    the signed-in user just like server-generated downloads. Any authenticated
    user may record their own export — reading the log stays admin-only."""
    await record_export(
        request, principal,
        resource_type=body.resource_type, resource_id=body.resource_id,
        resource_name=body.resource_name, fmt=body.format,
        count=body.count, detail=body.detail,
    )
    return {"recorded": True}


@router.get("", summary="List audit-log entries (filterable, paginated)")
async def list_audit(
    request: Request,
    action: str | None = Query(None, description="Exact action, e.g. 'export'"),
    user: str | None = Query(None, description="Match user name / id / key"),
    resource_type: str | None = Query(None, description="e.g. 'profile', 'fleet', 'node'"),
    q: str | None = Query(None, description="Free-text over resource name / path / detail"),
    date_from: str | None = Query(None, description="ISO date (inclusive)"),
    date_to: str | None = Query(None, description="ISO date (inclusive)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(require_admin),
):
    # Viewing the audit log shouldn't spam the audit log.
    request.state.audit_handled = True
    repo = _get_repo(request)
    if repo is None:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}
    df = date_from or None
    # date_to is a calendar day → extend to end-of-day so the whole day matches.
    dt = f"{date_to}T23:59:59.999999" if date_to else None
    items, total = await repo.find(
        action=action, user=user, resource_type=resource_type, q=q,
        date_from=df, date_to=dt, limit=limit, offset=offset,
    )
    for it in items:
        raw = it.get("detail")
        if raw:
            try:
                it["detail"] = json.loads(raw)
            except (ValueError, TypeError):
                pass
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/facets", summary="Distinct users / actions / resource types for filtering")
async def audit_facets(
    request: Request,
    principal: AuthPrincipal = Depends(require_admin),
):
    request.state.audit_handled = True
    repo = _get_repo(request)
    if repo is None:
        return {"users": [], "actions": [], "resource_types": []}
    return await repo.facets()
