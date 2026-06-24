from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.errors import NotFoundError, ConflictError, ForbiddenError, ValidationError
from interface.http.routes.auth import require_admin, get_current_principal

router = APIRouter(prefix="/node-groups", tags=["Node Groups"])

# ── Pydantic models ──────────────────────────────────────────────────────────

class RuleModel(BaseModel):
    fact: str
    operator: str = "="
    value: str = ""

class NodeGroupResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    parent: str = "All Nodes"
    environment: str = "production"
    is_environment_group: bool = False
    match_type: str = "all"
    rules: list[RuleModel] = []
    node_ids: list[str] = []           # pinned nodes
    matching_node_ids: list[str] = []  # pinned ∪ rule-matched
    puppet_group_id: str | None = None
    wazuh_synced: bool = False
    puppet_synced: bool = False
    group_type: str = "user"
    inspec_profile_id: str | None = None
    created_at: datetime
    updated_at: datetime

class CreateNodeGroupRequest(BaseModel):
    name: str
    description: str | None = None
    parent: str = "All Nodes"
    environment: str = "production"
    is_environment_group: bool = False
    match_type: str = "all"
    rules: list[RuleModel] = []
    node_ids: list[str] = []
    inspec_profile_id: str | None = None

class UpdateNodeGroupRequest(BaseModel):
    description: str | None = None
    parent: str | None = None
    environment: str | None = None
    is_environment_group: bool | None = None
    match_type: str | None = None
    rules: list[RuleModel] | None = None
    node_ids: list[str] | None = None

class AddNodeRequest(BaseModel):
    node_id: str

class FactResponse(BaseModel):
    name: str
    values: list[str] = []

class PreviewRequest(BaseModel):
    match_type: str = "all"
    rules: list[RuleModel] = []
    node_ids: list[str] = []

# ── Module-level use case holders ────────────────────────────────────────────

_list_uc = None
_get_uc = None
_create_uc = None
_update_uc = None
_delete_uc = None
_add_node_uc = None
_remove_node_uc = None
_facts_uc = None
_preview_uc = None
_seed_uc = None


def set_use_cases(list_uc, get_uc, create_uc, delete_uc, add_node_uc, remove_node_uc,
                  update_uc=None, facts_uc=None, preview_uc=None, seed_uc=None):
    global _list_uc, _get_uc, _create_uc, _update_uc, _delete_uc
    global _add_node_uc, _remove_node_uc, _facts_uc, _preview_uc, _seed_uc
    _list_uc = list_uc
    _get_uc = get_uc
    _create_uc = create_uc
    _update_uc = update_uc
    _delete_uc = delete_uc
    _add_node_uc = add_node_uc
    _remove_node_uc = remove_node_uc
    _facts_uc = facts_uc
    _preview_uc = preview_uc
    _seed_uc = seed_uc


def _resp(g, matching=None) -> NodeGroupResponse:
    return NodeGroupResponse(
        id=g.id, name=g.name, description=g.description,
        parent=g.parent, environment=g.environment,
        is_environment_group=g.is_environment_group,
        match_type=g.match_type,
        rules=[RuleModel(**r) for r in (g.rules or [])],
        node_ids=g.node_ids, matching_node_ids=matching or [],
        puppet_group_id=g.puppet_group_id,
        wazuh_synced=g.wazuh_synced, puppet_synced=g.puppet_synced,
        group_type=g.group_type,
        inspec_profile_id=g.inspec_profile_id,
        created_at=g.created_at, updated_at=g.updated_at,
    )

# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/seed-defaults", status_code=200)
async def seed_default_groups(principal=Depends(require_admin)):
    """Re-seed the built-in OS-family node group hierarchy (idempotent)."""
    created = await _seed_uc.execute()
    return {"created": created, "message": f"Seeded {created} new system groups"}


@router.get("", response_model=list[NodeGroupResponse])
async def list_node_groups(principal=Depends(get_current_principal)):
    return [_resp(g, matching) for g, matching in await _list_uc.execute()]


@router.get("/facts", response_model=list[FactResponse])
async def list_facts(principal=Depends(get_current_principal)):
    return [FactResponse(**f) for f in await _facts_uc.execute()]


@router.post("/preview", response_model=list[str])
async def preview_matching(body: PreviewRequest, principal=Depends(get_current_principal)):
    try:
        return await _preview_uc.execute(body.model_dump())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


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
        g, matching = await _get_uc.execute(id)
        return _resp(g, matching)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{id}", response_model=NodeGroupResponse)
async def update_node_group(id: str, body: UpdateNodeGroupRequest, principal=Depends(require_admin)):
    try:
        g = await _update_uc.execute(id, body.model_dump(exclude_unset=True))
        return _resp(g)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{id}")
async def delete_node_group(id: str, principal=Depends(require_admin)):
    try:
        return await _delete_uc.execute(id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


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
