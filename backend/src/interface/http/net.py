"""Client-IP resolution and login brute-force throttling.

The backend sits behind the frontend's nginx reverse proxy, so
``request.client.host`` is the proxy's address for every request. We trust
``X-Forwarded-For`` **only** when the immediate peer is a private/loopback
address (i.e. the internal proxy) — the backend is never directly exposed to
the internet — and otherwise fall back to the peer address. This makes both the
global rate limiter and the login throttle act per real client.
"""
from __future__ import annotations

import ipaddress
import threading
import time

from starlette.requests import Request


def _is_trusted_peer(ip: str | None) -> bool:
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.is_private or addr.is_loopback


def client_ip(request: Request) -> str:
    """Best-effort real client IP, honouring X-Forwarded-For behind the proxy."""
    peer = request.client.host if request.client else None
    if _is_trusted_peer(peer):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
    return peer or "unknown"


class LoginThrottle:
    """In-memory, per-(client-IP, username) failed-login lockout.

    Thread-safe (a plain lock — contention is negligible on the login path).
    State is per-process; behind multiple workers each process enforces its own
    counter, which is acceptable for a brute-force speed bump. On success the
    counters reset.
    """

    def __init__(self, max_failures: int = 5, window_seconds: int = 300, lockout_seconds: int = 900) -> None:
        self._max = max(1, int(max_failures))
        self._window = max(1, int(window_seconds))
        self._lockout = max(1, int(lockout_seconds))
        self._fails: dict[str, tuple[int, float]] = {}      # key -> (count, first_ts)
        self._locked_until: dict[str, float] = {}           # key -> unlock_ts
        self._lock = threading.Lock()

    @staticmethod
    def _key(ip: str, username: str) -> str:
        return f"{ip}|{(username or '').strip().lower()}"

    def seconds_locked(self, ip: str, username: str) -> int:
        """Remaining lockout in seconds, or 0 if not currently locked."""
        key = self._key(ip, username)
        now = time.monotonic()
        with self._lock:
            until = self._locked_until.get(key)
            if until is None:
                return 0
            if now >= until:
                self._locked_until.pop(key, None)
                return 0
            return int(until - now) + 1

    def record_failure(self, ip: str, username: str) -> None:
        key = self._key(ip, username)
        now = time.monotonic()
        with self._lock:
            count, first = self._fails.get(key, (0, now))
            if now - first > self._window:
                count, first = 0, now       # window elapsed → fresh count
            count += 1
            if count >= self._max:
                self._locked_until[key] = now + self._lockout
                self._fails.pop(key, None)
            else:
                self._fails[key] = (count, first)

    def record_success(self, ip: str, username: str) -> None:
        key = self._key(ip, username)
        with self._lock:
            self._fails.pop(key, None)
            self._locked_until.pop(key, None)
