"""The JWT signing secret is never the shipped insecure default."""
from __future__ import annotations

from modules.auth.usecases import DEFAULT_JWT_SECRET, resolve_jwt_secret


class FakeConfig:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value


async def test_uses_configured_strong_secret() -> None:
    cfg = FakeConfig()
    strong = "x" * 40
    assert await resolve_jwt_secret(strong, cfg) == strong
    assert "jwt_secret_auto" not in cfg.store  # nothing persisted when safe


async def test_generates_when_default() -> None:
    cfg = FakeConfig()
    got = await resolve_jwt_secret(DEFAULT_JWT_SECRET, cfg)
    assert got and got != DEFAULT_JWT_SECRET and len(got) >= 32
    assert cfg.store["jwt_secret_auto"] == got  # persisted for restart stability


async def test_generates_when_blank_or_short() -> None:
    assert len(await resolve_jwt_secret("", FakeConfig())) >= 32
    assert len(await resolve_jwt_secret("tooshort", FakeConfig())) >= 32


async def test_stable_across_calls() -> None:
    cfg = FakeConfig()
    assert await resolve_jwt_secret("", cfg) == await resolve_jwt_secret("", cfg)
