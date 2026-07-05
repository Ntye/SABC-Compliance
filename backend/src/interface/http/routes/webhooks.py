"""
Internal webhook endpoints.

These routes are NOT part of the operator-facing API and do not use the
Bearer-JWT scheme — they are called by infrastructure daemons running on the
managed nodes. They authenticate with a shared API key and an optional
source-IP allowlist instead.

The Wazuh alert receiver that used to live here was removed together with the
Wazuh integration; the custom detection agent's receiver
(POST /webhooks/detection) is wired in by main.py via set_use_cases().
"""
from __future__ import annotations

import hmac
import ipaddress
import logging

from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ── Dependency injection (set by main.py) ─────────────────────────────────────

_receive_detection_uc = None
_config_repo = None
_webhook_api_key_env: str | None = None
_allowed_sources_env: str | None = None


def set_use_cases(
    receive_detection_uc=None,
    config_repo=None,
    webhook_api_key: str | None = None,
    allowed_source_ips: str | None = None,
) -> None:
    global _receive_detection_uc, _config_repo, _webhook_api_key_env, _allowed_sources_env
    _receive_detection_uc = receive_detection_uc
    _config_repo = config_repo
    _webhook_api_key_env = webhook_api_key
    _allowed_sources_env = allowed_source_ips


# ── Authentication helpers ────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    """Best-effort source IP, honouring a single proxy hop (frontend nginx)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _parse_allowlist(raw: str | None) -> list[str]:
    """Comma/space separated list of IPs or CIDRs permitted to call the webhook."""
    return [s.strip() for s in (raw or "").replace(",", " ").split() if s.strip()]


def _source_allowed(ip: str, allowlist: list[str]) -> bool:
    if not allowlist:
        return True  # allowlist not configured → rely on the API key only
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in allowlist:
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


async def _config_value(key: str, env_fallback: str | None) -> str | None:
    """Platform-config value with env fallback (console-set value wins)."""
    if _config_repo is not None:
        try:
            val = await _config_repo.get(key)
            if val:
                return val
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Webhook config lookup failed for %s: %s", key, exc)
    return env_fallback


async def _authenticate(request: Request, api_key: str | None) -> None:
    """API-key + source-IP gate for the detection webhook.

    Closed by default: with no key configured the webhook refuses everything.
    """
    expected = await _config_value("detection_webhook_api_key", _webhook_api_key_env)
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Detection webhook is disabled (no detection_webhook_api_key configured).",
        )
    src = _client_ip(request)
    allowlist = _parse_allowlist(
        await _config_value("detection_webhook_source_ip", _allowed_sources_env)
    )
    if not _source_allowed(src, allowlist):
        logger.warning("Detection webhook rejected: source %s not in allowlist", src)
        raise HTTPException(status_code=403, detail="Source address not allowed")
    if not api_key or not hmac.compare_digest(api_key, expected):
        logger.warning("Detection webhook rejected: bad or missing API key from %s", src)
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/detection", summary="Receive a config-change event from a detection agent")
async def receive_detection_event(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    """
    Entry point of the detection plane. Managed nodes run the lightweight
    compliance detection agent, which POSTs one JSON document per file-change
    event (and a periodic heartbeat). The gateway stores the event as evidence,
    applies the feedback-storm suppression rules, and — for genuine drift —
    publishes `compliance.violation_detected` and triggers Puppet remediation.

    Returns 202 with the storage/suppression decision; 404 when the reported
    node_hostname does not match a registered node.
    """
    await _authenticate(request, x_api_key)

    if _receive_detection_uc is None:
        raise HTTPException(status_code=503, detail="Detection receiver not initialised")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be valid JSON")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Event payload must be a JSON object")

    from core.errors import NotFoundError
    from fastapi.responses import JSONResponse
    try:
        result = await _receive_detection_uc.execute(payload)
    except NotFoundError as exc:
        logger.warning("Detection event for unknown node: %s", exc)
        raise HTTPException(status_code=404, detail=str(exc))
    return JSONResponse(status_code=202, content=result)
