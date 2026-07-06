from __future__ import annotations
import asyncio
import logging
import time
from datetime import datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Reads audit_repo from request.app.state — no constructor arg needed."""

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        audit_repo = getattr(request.app.state, "audit_repo", None)
        if audit_repo is None:
            return response

        # A route may have already written a rich, explicit audit entry for this
        # request (e.g. an export). Don't also write a generic duplicate.
        if getattr(request.state, "audit_handled", False):
            return response

        api_key_name = None
        x_key = request.headers.get("X-API-Key", "")
        if x_key:
            api_key_name = f"{x_key[:8]}..."

        # The auth dependency stashes the resolved principal on request.state so
        # every audited request is attributable to a real user (API key or JWT).
        principal = getattr(request.state, "principal", None)

        entry = {
            "ts": datetime.utcnow().isoformat(),
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "duration_ms": duration_ms,
            "api_key_name": api_key_name,
            "user_id": getattr(principal, "id", None),
            "user_name": getattr(principal, "name", None),
            "user_role": getattr(principal, "role", None),
        }
        asyncio.create_task(audit_repo.save(entry))
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_per_minute: int = 200) -> None:
        super().__init__(app)
        self._max = max_per_minute
        self._counts: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._cleaner_started = False

    async def _clear_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            async with self._lock:
                self._counts.clear()

    async def dispatch(self, request: Request, call_next):
        if not self._cleaner_started:
            self._cleaner_started = True
            asyncio.create_task(self._clear_loop())

        ip = request.client.host if request.client else "unknown"
        async with self._lock:
            self._counts[ip] = self._counts.get(ip, 0) + 1
            count = self._counts[ip]
        if count > self._max:
            return JSONResponse({"error": "Rate limit exceeded", "code": "RATE_LIMITED"}, status_code=429)
        return await call_next(request)
