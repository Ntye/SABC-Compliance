"""
Tier routes — criticality classification (Section 4).

Read is available to any authenticated principal; custom-tier mutation and node
tier assignment are RBAC-gated (admin) and audited by the HTTP audit middleware.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from interface.http.routes.auth import get_current_principal, require_admin, require_operator

router = APIRouter(prefix="/tiers", tags=["Tiers"])


class TierResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    includes_level_2: bool          # Axis 1 — validation scope
    enforce: bool                   # Axis 2 — auto-enforcement
    is_system: bool
    created_by: str | None = None
    extra_control_ids: list[str] = []
    created_at: datetime


class CreateTierRequest(BaseModel):
    name: str
    description: str | None = None
    includes_level_2: bool = False
    enforce: bool = False
    extra_control_ids: list[str] = []


class UpdateTierRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    includes_level_2: bool | None = None
    enforce: bool | None = None
    extra_control_ids: list[str] | None = None


class AssignTierRequest(BaseModel):
    tier_id: str


_list_uc = None
_get_uc = None
_create_uc = None
_update_uc = None
_delete_uc = None
_assign_uc = None
_assign_group_uc = None


def set_use_cases(list_uc=None, get_uc=None, create_uc=None, update_uc=None,
                  delete_uc=None, assign_uc=None, assign_group_uc=None) -> None:
    global _list_uc, _get_uc, _create_uc, _update_uc, _delete_uc, _assign_uc
    global _assign_group_uc
    _list_uc, _get_uc = list_uc, get_uc
    _create_uc, _update_uc, _delete_uc, _assign_uc = create_uc, update_uc, delete_uc, assign_uc
    _assign_group_uc = assign_group_uc


def _resp(t) -> TierResponse:
    return TierResponse(
        id=t.id, name=t.name, description=t.description,
        includes_level_2=t.includes_level_2, enforce=t.enforce, is_system=t.is_system,
        created_by=t.created_by, extra_control_ids=t.extra_control_ids,
        created_at=t.created_at,
    )


@router.get("", response_model=list[TierResponse], summary="List tiers")
async def list_tiers(principal: AuthPrincipal = Depends(get_current_principal)):
    return [_resp(t) for t in await _list_uc.execute()]


@router.get("/{tier_id}", response_model=TierResponse, summary="Get a tier")
async def get_tier(tier_id: str, principal: AuthPrincipal = Depends(get_current_principal)):
    try:
        return _resp(await _get_uc.execute(tier_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("", response_model=TierResponse, status_code=201,
             summary="Create a custom tier (admin)")
async def create_tier(body: CreateTierRequest,
                      principal: AuthPrincipal = Depends(require_admin)):
    """Custom tiers add individually-chosen CIS Level-2 controls on top of
    Level 1. Each extra control must be a real Level-2 control (rejected
    otherwise — controls are never invented)."""
    try:
        tier = await _create_uc.execute(body.model_dump(), created_by=getattr(principal, "name", None))
        return _resp(tier)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.patch("/{tier_id}", response_model=TierResponse, summary="Update a custom tier (admin)")
async def update_tier(tier_id: str, body: UpdateTierRequest,
                      principal: AuthPrincipal = Depends(require_admin)):
    try:
        return _resp(await _update_uc.execute(tier_id, body.model_dump(exclude_none=True)))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.delete("/{tier_id}", summary="Delete a custom tier (admin)")
async def delete_tier(tier_id: str, principal: AuthPrincipal = Depends(require_admin)):
    try:
        return await _delete_uc.execute(tier_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/assign/{node_id}", summary="Assign a node to a tier (audited)")
async def assign_node_tier(node_id: str, body: AssignTierRequest,
                           principal: AuthPrincipal = Depends(require_operator)):
    try:
        return await _assign_uc.execute(node_id, body.tier_id, actor=getattr(principal, "name", None))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/assign-group/{group_id}", summary="Assign every member of a node group to a tier (audited)")
async def assign_group_tier(group_id: str, body: AssignTierRequest,
                            principal: AuthPrincipal = Depends(require_operator)):
    """Stamp *tier_id* on every member of the Puppet node group. Tier is a
    per-node attribute, so this simply applies the same tier across the group —
    handy for classifying a whole environment at once."""
    if _assign_group_uc is None:
        raise HTTPException(status_code=503, detail="Group tier assignment not available")
    try:
        return await _assign_group_uc.execute(group_id, body.tier_id, actor=getattr(principal, "name", None))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
