"""Actor enrichment: ausearch parsing + login-uid → username resolution.

'Who made the change' must survive down to a name, not just a number, and
degrade cleanly when auditd is absent or the uid is unknown/unset.
"""
from __future__ import annotations

import subprocess

import pytest

import agent


# A trimmed but realistic `ausearch -f <path> --raw -ts recent` SYSCALL record.
_RAW_SYSCALL = (
    'type=SYSCALL msg=audit(1700000000.123:456): arch=c000003e syscall=257 '
    'success=yes exit=3 a0=ffffff9c a1=560f items=2 ppid=1200 pid=1234 '
    'auid=1000 uid=0 gid=0 euid=0 comm="vim" exe="/usr/bin/vim" '
    'subj=unconfined key="sabc-watch"'
)


def _fake_run(stdout: str, returncode: int = 0):
    def _run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")
    return _run


class TestResolveUsername:
    def test_resolves_known_uid(self, monkeypatch) -> None:
        import pwd

        monkeypatch.setattr(pwd, "getpwuid", lambda uid: type("P", (), {"pw_name": "alice"}))
        assert agent._resolve_username(1000) == "alice"

    def test_unset_auid_is_none(self) -> None:
        assert agent._resolve_username(agent._AUID_UNSET) is None

    def test_unknown_uid_is_none(self, monkeypatch) -> None:
        import pwd

        def _raise(_uid):
            raise KeyError("no such uid")
        monkeypatch.setattr(pwd, "getpwuid", _raise)
        assert agent._resolve_username(4242) is None

    @pytest.mark.parametrize("bad", [None, -1, "1000", 1.0])
    def test_non_uid_inputs_are_none(self, bad) -> None:
        assert agent._resolve_username(bad) is None


class TestLookupActor:
    def test_parses_fields_and_resolves_login_user(self, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_run(_RAW_SYSCALL))
        monkeypatch.setattr(agent, "_resolve_username",
                            lambda uid: "alice" if uid == 1000 else None)
        actor = agent.lookup_actor("/etc/passwd")
        assert actor == {
            "auid": 1000, "uid": 0, "exe": "/usr/bin/vim",
            "comm": "vim", "username": "alice",
        }

    def test_falls_back_to_uid_when_auid_unset(self, monkeypatch) -> None:
        raw = _RAW_SYSCALL.replace("auid=1000", f"auid={agent._AUID_UNSET}")
        monkeypatch.setattr(subprocess, "run", _fake_run(raw))
        # login uid unset → resolve the effective uid (0 → root) instead.
        monkeypatch.setattr(agent, "_resolve_username",
                            lambda uid: "root" if uid == 0 else None)
        actor = agent.lookup_actor("/etc/passwd")
        assert actor["auid"] == agent._AUID_UNSET
        assert actor["username"] == "root"

    def test_missing_ausearch_returns_none(self, monkeypatch) -> None:
        def _boom(*a, **k):
            raise FileNotFoundError("ausearch not installed")
        monkeypatch.setattr(subprocess, "run", _boom)
        assert agent.lookup_actor("/etc/passwd") is None

    def test_nonzero_returncode_returns_none(self, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_run("", returncode=1))
        assert agent.lookup_actor("/etc/passwd") is None

    def test_no_username_key_when_unresolvable(self, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_run(_RAW_SYSCALL))
        monkeypatch.setattr(agent, "_resolve_username", lambda uid: None)
        actor = agent.lookup_actor("/etc/passwd")
        assert actor is not None and "username" not in actor
