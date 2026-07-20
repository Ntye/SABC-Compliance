"""Hash-only snapshot policy resolution."""
from __future__ import annotations

import pytest

from agent import SnapshotPolicy


@pytest.fixture()
def default_policy() -> SnapshotPolicy:
    return SnapshotPolicy()


class TestBuiltinDefaults:
    def test_shadow_is_hash_only(self, default_policy: SnapshotPolicy) -> None:
        assert default_policy.resolve("/etc/shadow") == SnapshotPolicy.HASH_ONLY

    @pytest.mark.parametrize("path", [
        "/etc/ssh/ssh_host_rsa_key",          # *key*
        "/etc/ssh/ssh_host_ed25519_key",
        "/root/.ssh/authorized_keys",          # contains "key"
        "/etc/pki/tls/private/server.pem",     # *.pem
        "/etc/pki/tls/certs/server.crt",       # *.crt
        "/etc/ssl/MyKey.PEM",                  # case-insensitive basename
    ])
    def test_private_material_is_hash_only(self, default_policy: SnapshotPolicy, path: str) -> None:
        assert default_policy.resolve(path) == SnapshotPolicy.HASH_ONLY

    @pytest.mark.parametrize("path", [
        "/etc/ssh/sshd_config",
        "/etc/passwd",
        "/etc/group",
        "/etc/sudoers",
        "/etc/sudoers.d/90-cloud-init-users",
        "/etc/pam.d/sshd",
    ])
    def test_everything_else_is_full(self, default_policy: SnapshotPolicy, path: str) -> None:
        assert default_policy.resolve(path) == SnapshotPolicy.FULL


class TestConfigRules:
    def test_explicit_hash_only_rule(self) -> None:
        policy = SnapshotPolicy([{"path": "/etc/passwd", "snapshot": "hash-only"}])
        assert policy.resolve("/etc/passwd") == SnapshotPolicy.HASH_ONLY

    def test_explicit_rule_overrides_builtin_default(self) -> None:
        # An operator may deliberately allow full snapshots of a cert file.
        policy = SnapshotPolicy([{"path": "/etc/pki/tls/certs/server.crt", "snapshot": "full"}])
        assert policy.resolve("/etc/pki/tls/certs/server.crt") == SnapshotPolicy.FULL

    def test_directory_prefix_rule_applies_to_children(self) -> None:
        policy = SnapshotPolicy([{"path": "/etc/secrets", "snapshot": "hash-only"}])
        assert policy.resolve("/etc/secrets/db.conf") == SnapshotPolicy.HASH_ONLY
        assert policy.resolve("/etc/secretsfile") == SnapshotPolicy.FULL  # not a child

    def test_most_specific_rule_wins(self) -> None:
        policy = SnapshotPolicy([
            {"path": "/etc/app", "snapshot": "hash-only"},
            {"path": "/etc/app/public.conf", "snapshot": "full"},
        ])
        assert policy.resolve("/etc/app/private.conf") == SnapshotPolicy.HASH_ONLY
        assert policy.resolve("/etc/app/public.conf") == SnapshotPolicy.FULL

    def test_glob_rule_on_basename(self) -> None:
        policy = SnapshotPolicy([{"path": "*.secret", "snapshot": "hash-only"}])
        assert policy.resolve("/opt/app/database.secret") == SnapshotPolicy.HASH_ONLY

    def test_invalid_mode_falls_back_to_full(self) -> None:
        policy = SnapshotPolicy([{"path": "/etc/motd", "snapshot": "nonsense"}])
        assert policy.resolve("/etc/motd") == SnapshotPolicy.FULL
