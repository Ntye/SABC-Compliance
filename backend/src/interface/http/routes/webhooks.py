"""
Internal webhook endpoints.

These routes are NOT part of the operator-facing API and do not use the
X-API-Key / Bearer JWT scheme — they are called by infrastructure daemons
(currently the Wazuh manager's integrator). They authenticate with a shared
secret header and an optional source-IP allowlist instead.

    Wazuh integrator  ──POST /api/webhooks/wazuh──▶  ReceiveWazuhAlertUseCase
                          X-Wazuh-Webhook-Token: <secret>

Wiring the Wazuh side (on the manager), /var/ossec/etc/ossec.conf:

    <integration>
      <name>custom-sabc</name>
      <hook_url>https://platform:8443/api/webhooks/wazuh</hook_url>
      <level>7</level>
      <alert_format>json</alert_format>
      <api_key>REPLACE_WITH_wazuh_webhook_secret</api_key>
    </integration>

The companion script /var/ossec/integrations/custom-sabc forwards each alert as
JSON with the header  X-Wazuh-Webhook-Token: <api_key>.
"""
from __future__ import annotations

import hmac
import ipaddress
import logging

from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ── Dependency injection (set by main.py) ─────────────────────────────────────

_receive_wazuh_uc = None
_webhook_secret: str | None = None
_allowed_sources: list[str] = []


def set_use_cases(receive_wazuh_uc=None, webhook_secret: str | None = None,
                  allowed_source_ips: str | None = None) -> None:
    global _receive_wazuh_uc, _webhook_secret, _allowed_sources
    _receive_wazuh_uc = receive_wazuh_uc
    _webhook_secret = webhook_secret
    # Comma/space separated list of IPs or CIDRs permitted to call the webhook.
    _allowed_sources = [
        s.strip() for s in (allowed_source_ips or "").replace(",", " ").split() if s.strip()
    ]


# ── Authentication helpers ────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    """Best-effort source IP, honouring a single proxy hop (frontend nginx)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _source_allowed(ip: str) -> bool:
    if not _allowed_sources:
        return True  # allowlist not configured → rely on the shared secret only
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in _allowed_sources:
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def _authenticate(request: Request, token: str | None) -> None:
    # Closed by default: with no secret configured the webhook refuses everything.
    if not _webhook_secret:
        raise HTTPException(
            status_code=503,
            detail="Wazuh webhook is disabled (set wazuh_webhook_secret to enable).",
        )
    src = _client_ip(request)
    if not _source_allowed(src):
        logger.warning("Wazuh webhook rejected: source %s not in allowlist", src)
        raise HTTPException(status_code=403, detail="Source address not allowed")
    if not token or not hmac.compare_digest(token, _webhook_secret):
        logger.warning("Wazuh webhook rejected: bad or missing token from %s", src)
        raise HTTPException(status_code=401, detail="Invalid webhook token")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/wazuh", summary="Receive a Wazuh alert and drive the remediation loop")
async def receive_wazuh_alert(
    request: Request,
    x_wazuh_webhook_token: str | None = Header(None, alias="X-Wazuh-Webhook-Token"),
):
    """
    Entry point of the closed remediation loop. Authenticated by shared secret
    (and optional source-IP allowlist), this accepts a raw Wazuh alert document,
    resolves it to a managed node, and schedules a Puppet enforcement run
    followed by an automatic compliance re-scan. Returns 202 immediately so the
    Wazuh integrator is never blocked on the length of a Puppet run.
    """
    _authenticate(request, x_wazuh_webhook_token)

    if _receive_wazuh_uc is None:
        raise HTTPException(status_code=503, detail="Webhook receiver not initialised")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be valid JSON")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Alert payload must be a JSON object")

    result = await _receive_wazuh_uc.execute(payload)
    status_code = 202 if result.get("status") in ("accepted", "queued", "skipped") else 200
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status_code, content=result)
