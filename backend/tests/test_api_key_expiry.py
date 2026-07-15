"""Temporal API keys: a key authenticates only inside its start/end window,
so revocation at the end date is automatic (enforced at authentication time,
no background sweep). Unbounded keys (both dates None) never expire."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.domain.entities import ApiKey
from core.errors import UnauthorizedError, ValidationError
from modules.auth.usecases import (
    AuthenticateUseCase, CreateApiKeyUseCase, _hash_key,
)


class FakeApiKeyRepo:
    def __init__(self) -> None:
        self.keys: list[ApiKey] = []

    async def save(self, key: ApiKey) -> None:
        self.keys.append(key)

    async def find_by_hash(self, h: str) -> ApiKey | None:
        return next((k for k in self.keys if k.key_hash == h), None)

    async def touch_last_used(self, id: str) -> None:
        pass


def _now() -> datetime:
    return datetime.utcnow()


async def _make(repo, **window) -> str:
    uc = CreateApiKeyUseCase(repo)
    res = await uc.execute({"name": "k", "role": "admin", **window})
    return res["api_key"]


class TestWindowEnforcement:
    async def test_key_in_window_authenticates(self) -> None:
        repo = FakeApiKeyRepo()
        raw = await _make(repo,
                          starts_at=(_now() - timedelta(hours=1)).isoformat(),
                          expires_at=(_now() + timedelta(hours=1)).isoformat())
        key = await AuthenticateUseCase(repo).execute(raw)
        assert key.name == "k"

    async def test_expired_key_is_rejected(self) -> None:
        repo = FakeApiKeyRepo()
        raw = await _make(repo,
                          starts_at=(_now() - timedelta(days=2)).isoformat(),
                          expires_at=(_now() - timedelta(days=1)).isoformat())
        with pytest.raises(UnauthorizedError, match="expired"):
            await AuthenticateUseCase(repo).execute(raw)

    async def test_not_yet_valid_key_is_rejected(self) -> None:
        repo = FakeApiKeyRepo()
        raw = await _make(repo,
                          starts_at=(_now() + timedelta(days=1)).isoformat(),
                          expires_at=(_now() + timedelta(days=2)).isoformat())
        with pytest.raises(UnauthorizedError, match="not yet valid"):
            await AuthenticateUseCase(repo).execute(raw)

    async def test_unbounded_key_never_expires(self) -> None:
        repo = FakeApiKeyRepo()
        raw = await _make(repo)  # no window
        key = await AuthenticateUseCase(repo).execute(raw)
        assert key.expires_at is None and key.starts_at is None


class TestCreateValidation:
    async def test_end_before_start_rejected(self) -> None:
        repo = FakeApiKeyRepo()
        with pytest.raises(ValidationError):
            await _make(repo,
                        starts_at=_now().isoformat(),
                        expires_at=(_now() - timedelta(hours=1)).isoformat())


class TestEffectiveStatus:
    def test_status_transitions(self) -> None:
        now = _now()
        active = ApiKey(id="1", name="a", key_hash="h", role="admin", created_at=now,
                        starts_at=now - timedelta(hours=1), expires_at=now + timedelta(hours=1))
        expired = ApiKey(id="2", name="b", key_hash="h", role="admin", created_at=now,
                         expires_at=now - timedelta(hours=1))
        pending = ApiKey(id="3", name="c", key_hash="h", role="admin", created_at=now,
                         starts_at=now + timedelta(hours=1))
        revoked = ApiKey(id="4", name="d", key_hash="h", role="admin", created_at=now, active=False)
        assert active.effective_status(now) == "active"
        assert expired.effective_status(now) == "expired"
        assert pending.effective_status(now) == "pending"
        assert revoked.effective_status(now) == "revoked"
        # can_operate honours the window
        assert active.can_operate() and not expired.can_operate() and not pending.can_operate()
