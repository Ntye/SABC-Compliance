from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from jose import jwt, JWTError

from core.domain.entities import ApiKey, User, AuthPrincipal
from core.domain.interfaces import IApiKeyRepository, IUserRepository
from core.errors import (
    ConflictError, UnauthorizedError, ForbiddenError,
    ValidationError, NotFoundError,
)

if TYPE_CHECKING:
    pass


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _gen_key() -> str:
    return "bdc_" + secrets.token_hex(24)


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
    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

    async def execute(self) -> dict | None:
        if await self._repo.count_active() > 0:
            return None
        password = secrets.token_urlsafe(16)
        user = User(
            id=str(uuid.uuid4()),
            username="admin",
            password_hash=_hash_password(password),
            role="admin",
            created_at=datetime.utcnow(),
        )
        await self._repo.save(user)
        return {"username": "admin", "password": password, "role": "admin"}


class LoginUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        jwt_secret: str,
        jwt_algorithm: str,
        jwt_expire_hours: int,
    ) -> None:
        self._repo = user_repo
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
        expire = datetime.utcnow() + timedelta(hours=self._expire_hours)
        token = jwt.encode(
            {"sub": user.id, "username": user.username, "role": user.role, "exp": expire},
            self._secret,
            algorithm=self._algorithm,
        )
        return {"access_token": token, "token_type": "bearer", "role": user.role, "username": user.username}


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
        return AuthPrincipal(id=user.id, name=user.username, role=user.role, source="jwt")


class CreateUserUseCase:
    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

    async def execute(self, data: dict) -> User:
        username = data.get("username", "").strip()
        password = data.get("password", "")
        role = data.get("role", "readonly")
        email = data.get("email")
        if not username or not password:
            raise ValidationError("username and password are required")
        if role not in User.ROLES:
            raise ValidationError(f"role must be one of {User.ROLES}")
        existing = await self._repo.find_by_username(username)
        if existing:
            raise ConflictError(f"User '{username}' already exists")
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            password_hash=_hash_password(password),
            role=role,
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
