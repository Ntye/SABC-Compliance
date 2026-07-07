"""Stdlib polling fallback: the watcher used when watchdog is not installed.

Proves the agent detects create/modify/delete with zero third-party deps, so it
can run on any node with just python3 (no pip, no distro package, airgap-safe).
"""
from __future__ import annotations

import os

import pytest

from agent import AgentConfig, _build_watcher, _enumerate_targets, _PollingWatcher


class FakeDebouncer:
    def __init__(self) -> None:
        self.offers: list[tuple[str, str]] = []

    def offer(self, path: str, event_type: str) -> None:
        self.offers.append((os.path.normpath(path), event_type))


def _config(tmp_path, **kw) -> AgentConfig:
    return AgentConfig(
        gateway_url="https://gw/api", api_key="k", node_hostname="n",
        watch_paths=[str(tmp_path)], **kw,
    )


def _sig(path: str) -> tuple:
    st = os.stat(path)
    return (st.st_mtime_ns, st.st_size, st.st_ino)


class TestEnumerateTargets:
    def test_dir_vs_file_split(self, tmp_path) -> None:
        d = tmp_path / "etcssh"; d.mkdir()
        f = tmp_path / "sudoers"; f.write_text("x")
        dirs, files = _enumerate_targets([str(d), str(f)])
        assert str(d) in dirs
        assert os.path.normpath(str(f)) in files[str(tmp_path)]


class TestPollingWatcher:
    def test_seeds_silently_then_detects_created(self, tmp_path) -> None:
        deb = FakeDebouncer()
        w = _PollingWatcher(_config(tmp_path), deb)
        # start() seeds the baseline WITHOUT emitting (no replay on restart)
        w._sigs = w._scan()
        assert deb.offers == []

        (tmp_path / "new.conf").write_text("hello")
        w._emit_changes(w._scan())
        assert (os.path.normpath(str(tmp_path / "new.conf")), "created") in deb.offers

    def test_detects_modified(self, tmp_path) -> None:
        f = tmp_path / "sshd_config"; f.write_text("Port 22\n")
        deb = FakeDebouncer()
        w = _PollingWatcher(_config(tmp_path), deb)
        w._sigs = w._scan()

        # Force a distinct mtime so the signature changes deterministically.
        st = f.stat()
        f.write_text("Port 2222\nPermitRootLogin no\n")
        os.utime(f, ns=(st.st_mtime_ns + 10_000_000, st.st_mtime_ns + 10_000_000))
        w._emit_changes(w._scan())
        assert (os.path.normpath(str(f)), "modified") in deb.offers

    def test_detects_deleted(self, tmp_path) -> None:
        f = tmp_path / "gone"; f.write_text("x")
        deb = FakeDebouncer()
        w = _PollingWatcher(_config(tmp_path), deb)
        w._sigs = w._scan()

        f.unlink()
        w._emit_changes(w._scan())
        assert (os.path.normpath(str(f)), "deleted") in deb.offers

    def test_unchanged_files_are_quiet(self, tmp_path) -> None:
        (tmp_path / "stable").write_text("x")
        deb = FakeDebouncer()
        w = _PollingWatcher(_config(tmp_path), deb)
        w._sigs = w._scan()
        w._emit_changes(w._scan())   # nothing changed
        assert deb.offers == []

    def test_recurses_into_watched_directories(self, tmp_path) -> None:
        sub = tmp_path / "pam.d"; sub.mkdir()
        deb = FakeDebouncer()
        w = _PollingWatcher(_config(tmp_path), deb)
        w._sigs = w._scan()
        (sub / "sshd").write_text("auth required pam_unix.so")
        w._emit_changes(w._scan())
        assert (os.path.normpath(str(sub / "sshd")), "created") in deb.offers

    def test_watcher_surface_is_observer_compatible(self, tmp_path) -> None:
        w = _PollingWatcher(_config(tmp_path), FakeDebouncer())
        # start/stop/join must exist and not raise (daemon thread, quick stop).
        w.start()
        w.stop()
        w.join(timeout=2)


class TestBackendSelection:
    def test_falls_back_to_polling_without_watchdog(self, tmp_path, monkeypatch) -> None:
        import builtins
        real_import = builtins.__import__

        def _no_watchdog(name, *a, **k):
            if name == "watchdog" or name.startswith("watchdog."):
                raise ImportError("simulated: watchdog not installed")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", _no_watchdog)
        w = _build_watcher(_config(tmp_path), FakeDebouncer())
        assert isinstance(w, _PollingWatcher)
