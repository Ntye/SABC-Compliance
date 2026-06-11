from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.errors import NotFoundError, ConflictError, ValidationError
from interface.http.routes.auth import require_admin, get_current_principal

router = APIRouter(prefix="/node-groups", tags=["Node Groups"])

# ── Pydantic models ──────────────────────────────────────────────────────────

class NodeGroupResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    node_ids: list[str] = []
    puppet_group_id: str | None = None
    wazuh_synced: bool = False
    puppet_synced: bool = False
    created_at: datetime
    updated_at: datetime

class CreateNodeGroupRequest(BaseModel):
    name: str
    description: str | None = None

class AddNodeRequest(BaseModel):
    node_id: str

# ── Module-level use case holders ────────────────────────────────────────────

_list_uc = None
_get_uc = None
_create_uc = None
_delete_uc = None
_add_node_uc = None
_remove_node_uc = None


def set_use_cases(list_uc, get_uc, create_uc, delete_uc, add_node_uc, remove_node_uc):
    global _list_uc, _get_uc, _create_uc, _delete_uc, _add_node_uc, _remove_node_uc
    _list_uc = list_uc
    _get_uc = get_uc
    _create_uc = create_uc
    _delete_uc = delete_uc
    _add_node_uc = add_node_uc
    _remove_node_uc = remove_node_uc


def _resp(g) -> NodeGroupResponse:
    return NodeGroupResponse(
        id=g.id, name=g.name, description=g.description,
        node_ids=g.node_ids, puppet_group_id=g.puppet_group_id,
        wazuh_synced=g.wazuh_synced, puppet_synced=g.puppet_synced,
        created_at=g.created_at, updated_at=g.updated_at,
    )

# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NodeGroupResponse])
async def list_node_groups(principal=Depends(get_current_principal)):
    return [_resp(g) for g in await _list_uc.execute()]


@router.post("", status_code=201, response_model=NodeGroupResponse)
async def create_node_group(body: CreateNodeGroupRequest, principal=Depends(require_admin)):
    try:
        g = await _create_uc.execute(body.model_dump())
        return _resp(g)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{id}", response_model=NodeGroupResponse)
async def get_node_group(id: str, principal=Depends(get_current_principal)):
    try:
        return _resp(await _get_uc.execute(id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{id}")
async def delete_node_group(id: str, principal=Depends(require_admin)):
    try:
        return await _delete_uc.execute(id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{id}/nodes")
async def add_node(id: str, body: AddNodeRequest, principal=Depends(require_admin)):
    try:
        return await _add_node_uc.execute(id, body.node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{id}/nodes/{node_id}")
async def remove_node(id: str, node_id: str, principal=Depends(require_admin)):
    try:
        return await _remove_node_uc.execute(id, node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
