"""Detection webhook authentication: shared API key + source-IP allowlist.

Closed by default: no configured key -> 503 for everyone. With a key:
wrong/missing key -> 401, source not in the CIDR allowlist -> 403,
empty allowlist -> any authenticated source is accepted.
"""
from __future__ import annotations

from typing import Optional

import pytest
from fastapi import HTTPException

from interface.http.routes import webhooks


class FakeRequest:
    """Just enough of starlette.Request for _client_ip()."""

    def __init__(self, client_ip: str = "10.0.0.5",
                 forwarded_for: Optional[str] = None) -> None:
        self.headers = {}
        if forwarded_for:
            self.headers["x-forwarded-for"] = forwarded_for
        self.client = type("Client", (), {"host": client_ip})()


class FakeConfigRepo:
    def __init__(self, values: Optional[dict[str, str]] = None) -> None:
        self._values = values or {}

    async def get(self, key: str) -> Optional[str]:
        return self._values.get(key)


def configure(api_key: Optional[str] = None,
              allowlist: Optional[str] = None,
              config_values: Optional[dict[str, str]] = None) -> None:
    webhooks.set_use_cases(
        receive_detection_uc=object(),
        config_repo=FakeConfigRepo(config_values),
        webhook_api_key=api_key,
        allowed_source_ips=allowlist,
    )


async def auth(request: FakeRequest, key: Optional[str]) -> None:
    await webhooks._authenticate(request, key)  # type: ignore[arg-type]


# ── Closed by default ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_key_configured_returns_503_for_everyone() -> None:
    configure(api_key=None)
    with pytest.raises(HTTPException) as exc:
        await auth(FakeRequest(), "whatever")
    assert exc.value.status_code == 503


# ── API key gate ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_key_passes() -> None:
    configure(api_key="sabcdet_secret")
    await auth(FakeRequest(), "sabcdet_secret")   # must not raise


@pytest.mark.asyncio
@pytest.mark.parametrize("presented", [None, "", "wrong", "sabcdet_secret2"])
async def test_bad_or_missing_key_is_401(presented: Optional[str]) -> None:
    configure(api_key="sabcdet_secret")
    with pytest.raises(HTTPException) as exc:
        await auth(FakeRequest(), presented)
    assert exc.value.status_code == 401


# ── Source-IP allowlist ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_allowlist_allows_any_authenticated_source() -> None:
    configure(api_key="k", allowlist="")
    await auth(FakeRequest(client_ip="203.0.113.99"), "k")


@pytest.mark.asyncio
async def test_cidr_allowlist_accepts_member_ip() -> None:
    configure(api_key="k", allowlist="10.0.0.0/24, 192.168.1.10")
    await auth(FakeRequest(client_ip="10.0.0.5"), "k")
    await auth(FakeRequest(client_ip="192.168.1.10"), "k")


@pytest.mark.asyncio
async def test_cidr_allowlist_rejects_outsider_with_403() -> None:
    configure(api_key="k", allowlist="10.0.0.0/24")
    with pytest.raises(HTTPException) as exc:
        await auth(FakeRequest(client_ip="203.0.113.99"), "k")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_ip_check_runs_before_key_check() -> None:
    # A blocked source gets 403 even with a bad key — no key oracle for
    # sources that are not allowed to talk to us at all.
    configure(api_key="k", allowlist="10.0.0.0/24")
    with pytest.raises(HTTPException) as exc:
        await auth(FakeRequest(client_ip="203.0.113.99"), "wrong")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_forwarded_for_header_is_honoured() -> None:
    # Behind the frontend nginx the real source arrives in X-Forwarded-For.
    configure(api_key="k", allowlist="10.0.0.0/24")
    ok = FakeRequest(client_ip="172.18.0.2", forwarded_for="10.0.0.7")
    await auth(ok, "k")
    bad = FakeRequest(client_ip="172.18.0.2", forwarded_for="203.0.113.99")
    with pytest.raises(HTTPException) as exc:
        await auth(bad, "k")
    assert exc.value.status_code == 403


# ── Platform-config overrides env ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_config_db_key_wins_over_env_key() -> None:
    # The install flow stores the auto-generated key in platform_config; a
    # stale env value must not shadow it.
    configure(api_key="env-key",
              config_values={"detection_webhook_api_key": "db-key"})
    await auth(FakeRequest(), "db-key")
    with pytest.raises(HTTPException) as exc:
        await auth(FakeRequest(), "env-key")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_config_db_allowlist_is_used() -> None:
    configure(api_key="k",
              config_values={"detection_webhook_source_ip": "192.0.2.0/28"})
    await auth(FakeRequest(client_ip="192.0.2.5"), "k")
    with pytest.raises(HTTPException) as exc:
        await auth(FakeRequest(client_ip="192.0.3.5"), "k")
    assert exc.value.status_code == 403
