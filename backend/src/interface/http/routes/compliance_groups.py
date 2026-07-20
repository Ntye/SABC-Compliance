"""
Compliance node group routes (Section 5) — platform-only, RBAC-guarded.

These are DISTINCT from Puppet node groups (/node-groups) and never touch the
Puppet Node Classifier. A node may belong to several compliance groups and is
scanned against each group's bound profiles.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.errors import ConflictError, NotFoundError, ValidationError
from interface.http.routes.auth import get_current_principal, require_operator

router = APIRouter(prefix="/compliance-groups", tags=["Compliance Groups"])


class ComplianceGroupResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    profile_ids: list[str] = []
    node_ids: list[str] = []
    created_at: datetime
    updated_at: datetime


class CreateGroupRequest(BaseModel):
    name: str
    description: str | None = None
    profile_ids: list[str] = []
    node_ids: list[str] = []


class UpdateGroupRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    profile_ids: list[str] | None = None
    node_ids: list[str] | None = None


class MemberRequest(BaseModel):
    node_id: str


_list_uc = _get_uc = _create_uc = _update_uc = _delete_uc = None
_add_member_uc = _remove_member_uc = _scan_uc = None


def set_use_cases(list_uc=None, get_uc=None, create_uc=None, update_uc=None,
                  delete_uc=None, add_member_uc=None, remove_member_uc=None,
                  scan_uc=None) -> None:
    global _list_uc, _get_uc, _create_uc, _update_uc, _delete_uc
    global _add_member_uc, _remove_member_uc, _scan_uc
    _list_uc, _get_uc, _create_uc = list_uc, get_uc, create_uc
    _update_uc, _delete_uc = update_uc, delete_uc
    _add_member_uc, _remove_member_uc, _scan_uc = add_member_uc, remove_member_uc, scan_uc


def _resp(g) -> ComplianceGroupResponse:
    return ComplianceGroupResponse(
        id=g.id, name=g.name, description=g.description,
        profile_ids=g.profile_ids, node_ids=g.node_ids,
        created_at=g.created_at, updated_at=g.updated_at,
    )


@router.get("", response_model=list[ComplianceGroupResponse], summary="List compliance groups")
async def list_groups(principal: AuthPrincipal = Depends(get_current_principal)):
    return [_resp(g) for g in await _list_uc.execute()]


@router.get("/{group_id}", response_model=ComplianceGroupResponse, summary="Get a compliance group")
async def get_group(group_id: str, principal: AuthPrincipal = Depends(get_current_principal)):
    try:
        return _resp(await _get_uc.execute(group_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("", response_model=ComplianceGroupResponse, status_code=201,
             summary="Create a compliance group")
async def create_group(body: CreateGroupRequest,
                       principal: AuthPrincipal = Depends(require_operator)):
    try:
        return _resp(await _create_uc.execute(body.model_dump()))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.patch("/{group_id}", response_model=ComplianceGroupResponse, summary="Update a compliance group")
async def update_group(group_id: str, body: UpdateGroupRequest,
                       principal: AuthPrincipal = Depends(require_operator)):
    try:
        return _resp(await _update_uc.execute(group_id, body.model_dump(exclude_unset=True)))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.delete("/{group_id}", summary="Delete a compliance group")
async def delete_group(group_id: str, principal: AuthPrincipal = Depends(require_operator)):
    try:
        return await _delete_uc.execute(group_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{group_id}/scan", status_code=202,
             summary="Scan every member against the group's bound profiles")
async def scan_group(group_id: str, principal: AuthPrincipal = Depends(require_operator)):
    """Scan each member node against the group's bound profiles, with only the
    controls the node's tier makes applicable, in the node's OS family."""
    if _scan_uc is None:
        raise HTTPException(status_code=503, detail="Group scan not available")
    try:
        return await _scan_uc.execute(group_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{group_id}/members", response_model=ComplianceGroupResponse, summary="Add a node to a group")
async def add_member(group_id: str, body: MemberRequest,
                     principal: AuthPrincipal = Depends(require_operator)):
    try:
        return _resp(await _add_member_uc.execute(group_id, body.node_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{group_id}/members/{node_id}", response_model=ComplianceGroupResponse,
               summary="Remove a node from a group")
async def remove_member(group_id: str, node_id: str,
                        principal: AuthPrincipal = Depends(require_operator)):
    try:
        return _resp(await _remove_member_uc.execute(group_id, node_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
