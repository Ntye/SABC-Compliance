from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.errors import NotFoundError, ValidationError
from interface.http.routes.auth import get_current_principal, require_operator

router = APIRouter(prefix="/compliance", tags=["Compliance"])

# ── Pydantic models ───────────────────────────────────────────────────────────

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


@router.post("/nodes/{id}/collect", summary="Collect compliance data from an enrolled node")
async def collect_node_compliance(id: str, principal: AuthPrincipal = Depends(require_operator)):
    """
    Run CIS spot-checks over SSH (and read the Puppet last-run summary when the
    Puppet agent is enrolled), then store the results as compliance reports.
    Requires the node to be Puppet- or Wazuh-enrolled.
    """
    try:
        return await _collect_uc.execute(id)
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
