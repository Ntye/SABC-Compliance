from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.errors import NotFoundError, ValidationError
from interface.http.routes.auth import get_current_principal, require_operator

router = APIRouter(prefix="/compliance", tags=["Compliance"])

# ── Pydantic models ───────────────────────────────────────────────────────────

class CollectRequest(BaseModel):
    profile_id: str | None = None  # None/"all" → default; "cis-benchmark" or "sabc-linux-baseline"

class RemediateRequest(BaseModel):
    description: str | None = None


# ── Dependency injection (set by main.py) ─────────────────────────────────────

_summary_uc = None
_node_uc = None
_collect_uc = None
_remediate_uc = None


def set_use_cases(summary_uc, node_uc, collect_uc, remediate_uc) -> None:
    global _summary_uc, _node_uc, _collect_uc, _remediate_uc
    _summary_uc = summary_uc
    _node_uc = node_uc
    _collect_uc = collect_uc
    _remediate_uc = remediate_uc


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
