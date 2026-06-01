from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.errors import (
    ConflictError, ForbiddenError, UnauthorizedError, ValidationError,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

# ── Pydantic models ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str
    api_key: str

class ApiKeyResponse(BaseModel):
    id: str
    name: str
    role: str
    active: bool
    created_at: datetime
    last_used: datetime | None = None

class CreateApiKeyRequest(BaseModel):
    name: str
    role: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "readonly"
    email: str | None = None

class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    email: str | None = None
    active: bool
    created_at: datetime
    last_login: datetime | None = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

# ── Dependency factories (set by main.py via module-level vars) ───────────────

_authenticate_uc = None
_decode_jwt_uc = None
_init_api_key_uc = None
_create_api_key_uc = None
_list_api_keys_uc = None
_revoke_api_key_uc = None
_login_uc = None
_create_user_uc = None
_list_users_uc = None
_change_password_uc = None


def set_use_cases(
    authenticate_uc,
    decode_jwt_uc,
    init_api_key_uc,
    create_api_key_uc,
    list_api_keys_uc,
    revoke_api_key_uc,
    login_uc,
    create_user_uc,
    list_users_uc,
    change_password_uc,
) -> None:
    global _authenticate_uc, _decode_jwt_uc, _init_api_key_uc
    global _create_api_key_uc, _list_api_keys_uc, _revoke_api_key_uc
    global _login_uc, _create_user_uc, _list_users_uc, _change_password_uc
    _authenticate_uc = authenticate_uc
    _decode_jwt_uc = decode_jwt_uc
    _init_api_key_uc = init_api_key_uc
    _create_api_key_uc = create_api_key_uc
    _list_api_keys_uc = list_api_keys_uc
    _revoke_api_key_uc = revoke_api_key_uc
    _login_uc = login_uc
    _create_user_uc = create_user_uc
    _list_users_uc = list_users_uc
    _change_password_uc = change_password_uc


# ── Auth dependency ───────────────────────────────────────────────────────────

async def get_current_principal(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
) -> AuthPrincipal:
    """Authenticate via X-API-Key header or Authorization: Bearer JWT."""
    if x_api_key:
        try:
            key = await _authenticate_uc.execute(x_api_key)
            return AuthPrincipal(id=key.id, name=key.name, role=key.role, source="api_key")
        except UnauthorizedError as exc:
            raise HTTPException(status_code=401, detail=str(exc))

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            return await _decode_jwt_uc.execute(token)
        except UnauthorizedError as exc:
            raise HTTPException(status_code=401, detail=str(exc))

    raise HTTPException(status_code=401, detail="Authentication required (X-API-Key or Bearer token)")


async def require_operator(principal: AuthPrincipal = Depends(get_current_principal)) -> AuthPrincipal:
    """Require operator or admin role (API key or JWT)."""
    if not principal.can_operate():
        raise HTTPException(status_code=403, detail="Operator or admin role required")
    return principal


async def require_admin(principal: AuthPrincipal = Depends(get_current_principal)) -> AuthPrincipal:
    """Require admin role. JWT logins are allowed so admins can bootstrap keys."""
    if not principal.can_admin():
        raise HTTPException(status_code=403, detail="Admin role required")
    return principal


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login with username and password",
)
async def login(body: LoginRequest):
    """Authenticate with username and password. Returns a JWT Bearer token."""
    try:
        return await _login_uc.execute(body.username, body.password)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post(
    "/init",
    status_code=201,
    summary="Bootstrap first admin API key",
)
async def init_api_key():
    """Create the first admin API key. Returns 409 if keys already exist."""
    try:
        return await _init_api_key_uc.execute()
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get(
    "/keys",
    response_model=list[ApiKeyResponse],
    summary="List all API keys",
)
async def list_api_keys(principal: AuthPrincipal = Depends(require_admin)):
    """List all API keys (admin only)."""
    keys = await _list_api_keys_uc.execute()
    return [
        ApiKeyResponse(
            id=k.id, name=k.name, role=k.role, active=k.active,
            created_at=k.created_at, last_used=k.last_used,
        )
        for k in keys
    ]


@router.post(
    "/keys",
    status_code=201,
    summary="Create a new API key",
)
async def create_api_key(
    body: CreateApiKeyRequest,
    principal: AuthPrincipal = Depends(require_admin),
):
    """Create a new API key with the specified role (admin only)."""
    try:
        return await _create_api_key_uc.execute({"name": body.name, "role": body.role})
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete(
    "/keys/{id}",
    summary="Revoke an API key",
)
async def revoke_api_key(id: str, principal: AuthPrincipal = Depends(require_admin)):
    """Revoke an API key by ID (admin only)."""
    return await _revoke_api_key_uc.execute(id)


@router.get(
    "/users",
    response_model=list[UserResponse],
    summary="List all users",
)
async def list_users(principal: AuthPrincipal = Depends(require_admin)):
    """List all user accounts (admin only)."""
    users = await _list_users_uc.execute()
    return [
        UserResponse(
            id=u.id, username=u.username, role=u.role,
            email=u.email, active=u.active, created_at=u.created_at,
            last_login=u.last_login,
        )
        for u in users
    ]


@router.post(
    "/users",
    status_code=201,
    response_model=UserResponse,
    summary="Create a new user",
)
async def create_user(
    body: CreateUserRequest,
    principal: AuthPrincipal = Depends(require_admin),
):
    """Create a new user account (admin only)."""
    try:
        user = await _create_user_uc.execute({
            "username": body.username,
            "password": body.password,
            "role": body.role,
            "email": body.email,
        })
        return UserResponse(
            id=user.id, username=user.username, role=user.role,
            email=user.email, active=user.active, created_at=user.created_at,
            last_login=user.last_login,
        )
    except (ConflictError, ValidationError) as exc:
        raise HTTPException(status_code=409 if isinstance(exc, ConflictError) else 422, detail=str(exc))


@router.post(
    "/users/change-password",
    summary="Change current user's password",
)
async def change_password(
    body: ChangePasswordRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    """Change password for the currently authenticated user (JWT auth only)."""
    if principal.source != "jwt":
        raise HTTPException(status_code=400, detail="Password change only available for user accounts")
    try:
        return await _change_password_uc.execute(principal.id, body.old_password, body.new_password)
    except (UnauthorizedError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
