"""Login brute-force throttle + proxy-aware client-IP resolution."""
from __future__ import annotations

import time

from interface.http.net import LoginThrottle, client_ip


class FakeReq:
    def __init__(self, host, xff=None):
        self.client = type("C", (), {"host": host})()
        self.headers = {"x-forwarded-for": xff} if xff else {}


# ── client_ip ────────────────────────────────────────────────────────────────

def test_client_ip_trusts_xff_from_private_peer():
    # Behind the internal nginx proxy (private peer) → use the original client.
    assert client_ip(FakeReq("10.0.0.9", xff="203.0.113.7, 10.0.0.9")) == "203.0.113.7"


def test_client_ip_ignores_xff_from_public_peer():
    # A directly-connecting public peer can spoof XFF → ignore it. (8.8.8.8 is a
    # genuinely global address; note Python treats TEST-NET ranges as private.)
    assert client_ip(FakeReq("8.8.8.8", xff="1.2.3.4")) == "8.8.8.8"


def test_client_ip_no_xff():
    assert client_ip(FakeReq("10.0.0.9")) == "10.0.0.9"


# ── LoginThrottle ────────────────────────────────────────────────────────────

def test_lockout_after_threshold():
    t = LoginThrottle(max_failures=3, window_seconds=100, lockout_seconds=100)
    assert t.seconds_locked("1.1.1.1", "admin") == 0
    for _ in range(3):
        t.record_failure("1.1.1.1", "admin")
    assert t.seconds_locked("1.1.1.1", "admin") > 0


def test_success_resets_counter():
    t = LoginThrottle(max_failures=2, window_seconds=100, lockout_seconds=100)
    t.record_failure("1.1.1.1", "admin")
    t.record_success("1.1.1.1", "admin")
    t.record_failure("1.1.1.1", "admin")  # count restarts from zero
    assert t.seconds_locked("1.1.1.1", "admin") == 0


def test_lockout_expires():
    t = LoginThrottle(max_failures=1, window_seconds=100, lockout_seconds=1)
    t.record_failure("1.1.1.1", "admin")
    assert t.seconds_locked("1.1.1.1", "admin") > 0
    time.sleep(1.2)
    assert t.seconds_locked("1.1.1.1", "admin") == 0


def test_per_username_and_ip_isolation():
    t = LoginThrottle(max_failures=1, window_seconds=100, lockout_seconds=100)
    t.record_failure("1.1.1.1", "alice")
    assert t.seconds_locked("1.1.1.1", "alice") > 0
    assert t.seconds_locked("1.1.1.1", "bob") == 0      # other user unaffected
    assert t.seconds_locked("2.2.2.2", "alice") == 0    # other IP unaffected


def test_case_insensitive_username():
    t = LoginThrottle(max_failures=1, window_seconds=100, lockout_seconds=100)
    t.record_failure("1.1.1.1", "Admin")
    assert t.seconds_locked("1.1.1.1", "admin") > 0
