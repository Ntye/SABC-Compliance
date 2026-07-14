"""Secrets-at-rest: SecretBox round-trips, stays backward-compatible, fails safe."""
from __future__ import annotations

import os

from infrastructure.security.crypto import SecretBox, resolve_master_key


def test_round_trip() -> None:
    box = SecretBox("master-secret-abc")
    ct = box.encrypt("hunter2")
    assert ct != "hunter2"
    assert SecretBox.is_encrypted(ct)
    assert box.decrypt(ct) == "hunter2"


def test_plaintext_passthrough() -> None:
    box = SecretBox("m")
    # Legacy plaintext (no tag) is returned unchanged — DBs written before
    # encryption keep working.
    assert box.decrypt("legacy-plain") == "legacy-plain"
    assert box.decrypt(None) is None
    assert box.decrypt("") == ""


def test_empty_and_none_not_encrypted() -> None:
    box = SecretBox("m")
    assert box.encrypt("") == ""
    assert box.encrypt(None) is None


def test_no_double_wrap() -> None:
    box = SecretBox("m")
    once = box.encrypt("x")
    assert box.encrypt(once) == once


def test_wrong_key_fails_safe() -> None:
    ct = SecretBox("key-one").encrypt("secret")
    # A different key can't decrypt: return the stored value rather than raising.
    assert SecretBox("key-two").decrypt(ct) == ct


def test_resolve_master_key_explicit_wins(tmp_path) -> None:
    kf = str(tmp_path / "secret.key")
    assert resolve_master_key("explicit-key", kf) == "explicit-key"
    assert not os.path.exists(kf)  # explicit path never writes a file


def test_resolve_master_key_persists_0600(tmp_path) -> None:
    kf = str(tmp_path / "nested" / "secret.key")
    first = resolve_master_key("", kf)
    assert first and os.path.exists(kf)
    assert (os.stat(kf).st_mode & 0o777) == 0o600
    assert resolve_master_key("", kf) == first  # stable across restarts
