from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from jose import jwt, JWTError

from core.domain.entities import ApiKey, User, UserGroup, AuthPrincipal
from core.domain.interfaces import IApiKeyRepository, IUserRepository, IUserGroupRepository
from core.errors import (
    ConflictError, UnauthorizedError, ForbiddenError,
    ValidationError, NotFoundError,
)

if TYPE_CHECKING:
    pass


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _gen_key() -> str:
    return "sabc_" + secrets.token_hex(24)


def _hash_password(password: str) -> str:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return ctx.hash(password)


def _verify_password(password: str, hashed: str) -> bool:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return ctx.verify(password, hashed)


class InitApiKeyUseCase:
    def __init__(self, repo: IApiKeyRepository) -> None:
        self._repo = repo

    async def execute(self) -> dict:
        if await self._repo.count_active() > 0:
            raise ConflictError("API keys already exist")
        raw = _gen_key()
        key = ApiKey(
            id=str(uuid.uuid4()),
            name="default-admin",
            key_hash=_hash_key(raw),
            role="admin",
            created_at=datetime.utcnow(),
        )
        await self._repo.save(key)
        return {"api_key": raw, "role": "admin", "message": "Initial admin API key created. Store it securely — it will not be shown again."}


class AuthenticateUseCase:
    def __init__(self, repo: IApiKeyRepository) -> None:
        self._repo = repo

    async def execute(self, raw_key: str | None) -> ApiKey:
        if not raw_key:
            raise UnauthorizedError("API key required")
        found = await self._repo.find_by_hash(_hash_key(raw_key))
        if not found or not found.active:
            raise UnauthorizedError("Invalid or inactive API key")
        await self._repo.touch_last_used(found.id)
        return found


class CreateApiKeyUseCase:
    def __init__(self, repo: IApiKeyRepository) -> None:
        self._repo = repo

    async def execute(self, data: dict) -> dict:
        name = data.get("name", "").strip()
        role = data.get("role", "")
        if not name:
            raise ValidationError("name is required")
        if role not in ApiKey.ROLES:
            raise ValidationError(f"role must be one of {ApiKey.ROLES}")
        raw = _gen_key()
        key = ApiKey(
            id=str(uuid.uuid4()),
            name=name,
            key_hash=_hash_key(raw),
            role=role,
            created_at=datetime.utcnow(),
        )
        await self._repo.save(key)
        return {"id": key.id, "name": key.name, "role": key.role, "api_key": raw, "message": "Store this key securely — it will not be shown again."}


class ListApiKeysUseCase:
    def __init__(self, repo: IApiKeyRepository) -> None:
        self._repo = repo

    async def execute(self) -> list[ApiKey]:
        return await self._repo.find_all()


class RevokeApiKeyUseCase:
    def __init__(self, repo: IApiKeyRepository) -> None:
        self._repo = repo

    async def execute(self, id: str) -> dict:
        await self._repo.revoke(id)
        return {"message": f"API key {id} revoked"}


# ── Username / Password (JWT) auth ──────────────────────────────────────────

class InitAdminUserUseCase:
    def __init__(self, repo: IUserRepository, group_repo=None) -> None:
        self._repo = repo
        self._group_repo = group_repo

    async def execute(self) -> dict | None:
        if await self._repo.count_active() > 0:
            return None
        password = secrets.token_urlsafe(16)
        user = User(
            id=str(uuid.uuid4()),
            username="admin",
            password_hash=_hash_password(password),
            role="admin",  # kept for DB compat
            created_at=datetime.utcnow(),
        )
        await self._repo.save(user)
        if self._group_repo:
            admin_group = await self._group_repo.find_by_name("admin")
            if admin_group:
                await self._group_repo.add_member(admin_group.id, user.id)
        return {"username": "admin", "password": password}


class LoginUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        api_key_repo: IApiKeyRepository,
        group_repo: IUserGroupRepository,
        jwt_secret: str,
        jwt_algorithm: str,
        jwt_expire_hours: int,
    ) -> None:
        self._repo = user_repo
        self._api_key_repo = api_key_repo
        self._group_repo = group_repo
        self._secret = jwt_secret
        self._algorithm = jwt_algorithm
        self._expire_hours = jwt_expire_hours

    async def execute(self, username: str, password: str) -> dict:
        user = await self._repo.find_by_username(username)
        if not user or not user.active:
            raise UnauthorizedError("Invalid credentials")
        if not _verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid credentials")
        user.last_login = datetime.utcnow()
        await self._repo.update(user)

        # Aggregate permissions from all groups the user belongs to
        all_groups = await self._group_repo.find_all()
        perms: set[str] = set()
        for g in all_groups:
            if user.id in g.member_ids:
                perms.update(g.permissions)
        perms_list = sorted(perms)

        # Derive effective role for backward compat
        ADMIN_PERMS = {"manage_users", "manage_groups", "manage_node_groups"}
        OPERATOR_PERMS = {
            "ping_nodes", "register_nodes", "run_playbooks", "install_agents",
            "collect_compliance", "trigger_remediation", "cancel_jobs", "manage_api_keys",
        }
        if perms & ADMIN_PERMS:
            eff_role = "admin"
        elif perms & OPERATOR_PERMS:
            eff_role = "operator"
        else:
            eff_role = "readonly"

        expire = datetime.utcnow() + timedelta(hours=self._expire_hours)
        token = jwt.encode(
            {
                "sub": user.id,
                "username": user.username,
                "permissions": perms_list,
                "role": eff_role,
                "exp": expire,
            },
            self._secret,
            algorithm=self._algorithm,
        )
        # Revoke any previous personal key for this user, then issue a fresh one.
        await self._api_key_repo.revoke_by_user_id(user.id)
        raw = _gen_key()
        personal_key = ApiKey(
            id=str(uuid.uuid4()),
            name=f"personal-{user.username}",
            key_hash=_hash_key(raw),
            role=eff_role,
            created_at=datetime.utcnow(),
            user_id=user.id,
        )
        await self._api_key_repo.save(personal_key)
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": eff_role,
            "permissions": perms_list,
            "username": user.username,
            "api_key": raw,
        }


class DecodeJwtUseCase:
    def __init__(self, jwt_secret: str, jwt_algorithm: str, user_repo: IUserRepository) -> None:
        self._secret = jwt_secret
        self._algorithm = jwt_algorithm
        self._repo = user_repo

    async def execute(self, token: str) -> AuthPrincipal:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except JWTError:
            raise UnauthorizedError("Invalid or expired token")
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("Invalid token payload")
        user = await self._repo.find_by_id(user_id)
        if not user or not user.active:
            raise UnauthorizedError("User not found or inactive")
        permissions = payload.get("permissions", [])
        role = payload.get("role", "readonly")
        return AuthPrincipal(
            id=user.id,
            name=user.username,
            role=role,
            permissions=permissions,
            source="jwt",
        )


class CreateUserUseCase:
    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

    async def execute(self, data: dict) -> User:
        username = data.get("username", "").strip()
        password = data.get("password", "")
        email = data.get("email")
        if not username or not password:
            raise ValidationError("username and password are required")
        existing = await self._repo.find_by_username(username)
        if existing:
            raise ConflictError(f"User '{username}' already exists")
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            password_hash=_hash_password(password),
            role="",
            email=email,
            created_at=datetime.utcnow(),
        )
        await self._repo.save(user)
        return user


class ListUsersUseCase:
    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

    async def execute(self) -> list[User]:
        return await self._repo.find_all()


class ChangePasswordUseCase:
    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: str, old_password: str, new_password: str) -> dict:
        user = await self._repo.find_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        if not _verify_password(old_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect")
        if len(new_password) < 8:
            raise ValidationError("New password must be at least 8 characters")
        user.password_hash = _hash_password(new_password)
        await self._repo.update(user)
        return {"message": "Password changed successfully"}


async def require_role(principal: AuthPrincipal, *roles: str) -> None:
    if principal.role not in roles:
        raise ForbiddenError(f"Role '{principal.role}' is not allowed. Required: {roles}")


class UpdateUserUseCase:
    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: str, data: dict) -> User:
        user = await self._repo.find_by_id(user_id)
        if not user:
            raise NotFoundError(f"User '{user_id}' not found")
        if "email" in data:
            user.email = data.get("email")
        if "active" in data:
            user.active = bool(data["active"])
        await self._repo.update(user)
        return user


class DeleteUserUseCase:
    def __init__(self, repo: IUserRepository, api_key_repo: IApiKeyRepository) -> None:
        self._repo = repo
        self._key_repo = api_key_repo

    async def execute(self, user_id: str) -> dict:
        user = await self._repo.find_by_id(user_id)
        if not user:
            raise NotFoundError(f"User '{user_id}' not found")
        user.active = False
        await self._repo.update(user)
        await self._key_repo.revoke_by_user_id(user_id)
        return {"message": f"User '{user.username}' deactivated"}


class SeedDefaultGroupsUseCase:
    """Ensures the three immutable default groups exist on startup."""
    def __init__(self, repo) -> None:
        self._repo = repo

    async def execute(self) -> None:
        for name, cfg in UserGroup.DEFAULT_GROUPS.items():
            existing = await self._repo.find_by_name(name)
            if existing:
                continue
            group = UserGroup(
                id=str(uuid.uuid4()),
                name=name,
                description=cfg["description"],
                permissions=cfg["permissions"],
                is_default=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            await self._repo.save(group)


class CreateUserGroupUseCase:
    def __init__(self, repo) -> None:
        self._repo = repo

    async def execute(self, data: dict):
        name = data.get("name", "").strip()
        if not name:
            raise ValidationError("name is required")
        if name in UserGroup.DEFAULT_GROUPS:
            raise ConflictError(f"'{name}' is a reserved group name")
        perms = data.get("permissions", [])
        invalid = [p for p in perms if p not in UserGroup.ALL_PERMISSIONS]
        if invalid:
            raise ValidationError(f"Unknown permissions: {invalid}")
        group = UserGroup(
            id=str(uuid.uuid4()), name=name,
            description=data.get("description"),
            permissions=perms,
            is_default=False,
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        await self._repo.save(group)
        return group


class ListUserGroupsUseCase:
    def __init__(self, repo) -> None:
        self._repo = repo

    async def execute(self):
        return await self._repo.find_all()


class GetUserGroupUseCase:
    def __init__(self, repo) -> None:
        self._repo = repo

    async def execute(self, group_id: str):
        group = await self._repo.find_by_id(group_id)
        if not group:
            raise NotFoundError(f"Group '{group_id}' not found")
        return group


class UpdateUserGroupUseCase:
    def __init__(self, repo) -> None:
        self._repo = repo

    async def execute(self, group_id: str, data: dict):
        group = await self._repo.find_by_id(group_id)
        if not group:
            raise NotFoundError(f"Group '{group_id}' not found")
        if group.is_default:
            raise ForbiddenError("Default groups cannot be modified")
        if "name" in data and data["name"].strip():
            new_name = data["name"].strip()
            if new_name in UserGroup.DEFAULT_GROUPS:
                raise ValidationError(f"'{new_name}' is a reserved group name")
            group.name = new_name
        if "description" in data:
            group.description = data.get("description")
        if "permissions" in data:
            perms = data["permissions"] or []
            invalid = [p for p in perms if p not in UserGroup.ALL_PERMISSIONS]
            if invalid:
                raise ValidationError(f"Unknown permissions: {invalid}")
            group.permissions = perms
        group.updated_at = datetime.utcnow()
        await self._repo.update(group)
        return group


class DeleteUserGroupUseCase:
    def __init__(self, repo) -> None:
        self._repo = repo

    async def execute(self, group_id: str) -> dict:
        group = await self._repo.find_by_id(group_id)
        if not group:
            raise NotFoundError(f"Group '{group_id}' not found")
        if group.is_default:
            raise ForbiddenError("Default groups cannot be deleted")
        await self._repo.delete(group_id)
        return {"message": f"Group '{group.name}' deleted"}


class AddUserToGroupUseCase:
    def __init__(self, group_repo, user_repo: IUserRepository) -> None:
        self._group_repo = group_repo
        self._user_repo = user_repo

    async def execute(self, group_id: str, user_id: str) -> dict:
        group = await self._group_repo.find_by_id(group_id)
        if not group:
            raise NotFoundError(f"Group '{group_id}' not found")
        user = await self._user_repo.find_by_id(user_id)
        if not user:
            raise NotFoundError(f"User '{user_id}' not found")
        await self._group_repo.add_member(group_id, user_id)
        return {"message": f"User '{user.username}' added to group '{group.name}'"}


class RemoveUserFromGroupUseCase:
    def __init__(self, group_repo, user_repo: IUserRepository) -> None:
        self._group_repo = group_repo
        self._user_repo = user_repo

    async def execute(self, group_id: str, user_id: str) -> dict:
        group = await self._group_repo.find_by_id(group_id)
        if not group:
            raise NotFoundError(f"Group '{group_id}' not found")
        await self._group_repo.remove_member(group_id, user_id)
        return {"message": f"User removed from group '{group.name}'"}
