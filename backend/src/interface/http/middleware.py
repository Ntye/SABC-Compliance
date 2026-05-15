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
    def __init__(self, app, audit_repo) -> None:
        super().__init__(app)
        self._audit = audit_repo

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        api_key_name = None
        x_key = request.headers.get("X-API-Key", "")
        if x_key:
            api_key_name = f"{x_key[:8]}..."

        entry = {
            "ts": datetime.utcnow().isoformat(),
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "duration_ms": duration_ms,
            "api_key_name": api_key_name,
        }
        asyncio.create_task(self._audit.save(entry))
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_per_minute: int = 200) -> None:
        super().__init__(app)
        self._max = max_per_minute
        self._counts: dict[str, int] = {}
        self._lock = asyncio.Lock()
        asyncio.create_task(self._clear_loop())

    async def _clear_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            async with self._lock:
                self._counts.clear()

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        async with self._lock:
            self._counts[ip] = self._counts.get(ip, 0) + 1
            count = self._counts[ip]
        if count > self._max:
            return JSONResponse({"error": "Rate limit exceeded", "code": "RATE_LIMITED"}, status_code=429)
        return await call_next(request)
