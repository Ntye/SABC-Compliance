"""SSH host-key verification: TOFU into a shared known_hosts, never /dev/null."""
from __future__ import annotations

import os

from infrastructure.ssh.hardening import host_key_opts, known_hosts_path


def test_opts_use_accept_new(tmp_path) -> None:
    opts = host_key_opts(str(tmp_path / "keys" / "id_rsa"))
    joined = " ".join(opts)
    assert "StrictHostKeyChecking=accept-new" in opts
    assert "UserKnownHostsFile=" in joined
    assert "/dev/null" not in joined  # the old insecure setting is gone


def test_known_hosts_beside_key(tmp_path) -> None:
    key = str(tmp_path / "keys" / "id_rsa")
    assert known_hosts_path(key) == os.path.abspath(str(tmp_path / "keys" / "known_hosts"))


def test_known_hosts_is_absolute() -> None:
    assert os.path.isabs(known_hosts_path("relative/keys/id_rsa"))


def test_known_hosts_env_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SABC_KNOWN_HOSTS", str(tmp_path / "custom_kh"))
    assert known_hosts_path("/whatever/id_rsa") == os.path.abspath(str(tmp_path / "custom_kh"))


def test_creates_known_hosts_dir(tmp_path) -> None:
    host_key_opts(str(tmp_path / "newdir" / "id_rsa"))
    assert os.path.isdir(str(tmp_path / "newdir"))
