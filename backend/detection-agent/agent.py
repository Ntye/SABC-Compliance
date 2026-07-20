#!/usr/bin/env python3
"""
SABC Compliance Detection Agent.

A single lightweight daemon that runs on every managed node and forms the
detection plane of the SABC compliance platform (it replaces the old Wazuh
agent). It:

  1. watches a configurable list of compliance-critical paths with inotify
     (via the `watchdog` library — the only non-stdlib dependency);
  2. on every change, snapshots the file as EVIDENCE (SHA-256 + mode/uid/gid/
     size/mtime, plus the content itself where the per-path policy allows);
  3. tags the event when a Puppet agent run is in progress (the gateway uses
     this to suppress feedback storms — the agent itself never suppresses);
  4. best-effort enriches the event with the actor (auid/exe/comm) from
     auditd's ausearch, when auditd is available;
  5. POSTs each event to the platform gateway with retry + a local spool file
     so nothing is lost while the gateway is unreachable;
  6. sends a small heartbeat event every 10 minutes so the platform can show
     agent liveness.

Snapshots are evidence only — this agent never rolls anything back.

Configuration lives in /etc/compliance-agent/config.yaml (a deliberately
simple YAML subset parsed by this file so the stdlib-only constraint holds).

Run:  python3 agent.py --config /etc/compliance-agent/config.yaml
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import json
import logging
import os
import re
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Optional

logger = logging.getLogger("compliance-agent")

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_CONFIG_PATH = "/etc/compliance-agent/config.yaml"

DEFAULT_WATCH_PATHS: list[str] = [
    "/etc/ssh/",
    "/etc/pam.d/",
    "/etc/sudoers",
    "/etc/sudoers.d/",
    "/etc/passwd",
    "/etc/group",
    "/etc/shadow",
]

# Paths whose CONTENT must never leave the node (hashes + metadata only).
# /etc/shadow and anything that looks like private key material.
DEFAULT_HASH_ONLY_PATHS: list[str] = ["/etc/shadow"]
DEFAULT_HASH_ONLY_BASENAME_GLOBS: list[str] = ["*key*", "*.pem", "*.crt"]

PUPPET_LOCK_FILE = "/opt/puppetlabs/puppet/cache/state/agent_catalog_run.lock"

DEBOUNCE_SECONDS = 2.0
HEARTBEAT_INTERVAL_SECONDS = 600
MAX_SEND_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 1.0
MAX_CONTENT_BYTES = 256 * 1024  # full-snapshot files larger than this fall back to hash-only
# Stdlib polling fallback cadence when the inotify backend (watchdog) is absent.
# The watched set is small config dirs (/etc/ssh, /etc/pam.d, …), so a stat
# sweep every few seconds is negligible and keeps the agent dependency-free.
POLL_INTERVAL_SECONDS = 15.0


# ── Minimal YAML subset parser (stdlib-only constraint) ───────────────────────
#
# Supports exactly what the agent config needs: nested mappings by 2-space
# indentation, `- item` sequences (scalars or one-line mappings), scalars with
# optional quotes, booleans, ints, floats, and `#` comments. It is NOT a
# general YAML parser and never needs to be.

_SCALAR_TRUE = {"true", "yes", "on"}
_SCALAR_FALSE = {"false", "no", "off"}


def _parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if not s or s == "~" or s.lower() == "null":
        return None
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    low = s.lower()
    if low in _SCALAR_TRUE:
        return True
    if low in _SCALAR_FALSE:
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _strip_comment(line: str) -> str:
    """Remove a trailing comment, respecting simple quoting."""
    out: list[str] = []
    quote: Optional[str] = None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the simple YAML subset used by /etc/compliance-agent/config.yaml."""
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, stripped.strip()))

    def parse_block(start: int, indent: int) -> tuple[Any, int]:
        # Sequence block?
        if start < len(lines) and lines[start][0] == indent and lines[start][1].startswith("- "):
            seq: list[Any] = []
            i = start
            while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
                item = lines[i][1][2:].strip()
                if ":" in item and not item.startswith(("'", '"')):
                    # one-line mapping item: `- path: /etc/shadow` (+ continuation keys)
                    k, _, v = item.partition(":")
                    entry: dict[str, Any] = {k.strip(): _parse_scalar(v)}
                    i += 1
                    while i < len(lines) and lines[i][0] > indent and not lines[i][1].startswith("- "):
                        ck, _, cv = lines[i][1].partition(":")
                        entry[ck.strip()] = _parse_scalar(cv)
                        i += 1
                    seq.append(entry)
                else:
                    seq.append(_parse_scalar(item))
                    i += 1
            return seq, i

        # Mapping block
        mapping: dict[str, Any] = {}
        i = start
        while i < len(lines):
            line_indent, content = lines[i]
            if line_indent < indent:
                break
            if line_indent > indent:
                raise ValueError(f"Unexpected indent in config near: {content!r}")
            key, _, value = content.partition(":")
            key = key.strip()
            if value.strip():
                mapping[key] = _parse_scalar(value)
                i += 1
            else:
                # nested block (mapping or sequence) — or empty value
                if i + 1 < len(lines) and lines[i + 1][0] > line_indent:
                    child, i = parse_block(i + 1, lines[i + 1][0])
                    mapping[key] = child
                else:
                    mapping[key] = None
                    i += 1
        return mapping, i

    if not lines:
        return {}
    result, _ = parse_block(0, lines[0][0])
    if not isinstance(result, dict):
        raise ValueError("Top level of the agent config must be a mapping")
    return result


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class AgentConfig:
    gateway_url: str
    api_key: str
    node_hostname: str
    watch_paths: list[str] = field(default_factory=lambda: list(DEFAULT_WATCH_PATHS))
    snapshot_policies: list[dict[str, str]] = field(default_factory=list)
    verify_tls: bool = False
    debounce_seconds: float = DEBOUNCE_SECONDS
    heartbeat_interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS
    poll_interval_seconds: float = POLL_INTERVAL_SECONDS
    spool_dir: str = "/var/spool/compliance-agent"
    state_dir: str = "/var/lib/compliance-agent"
    max_content_bytes: int = MAX_CONTENT_BYTES

    @classmethod
    def load(cls, path: str) -> "AgentConfig":
        with open(path, "r", encoding="utf-8") as fh:
            raw = parse_simple_yaml(fh.read())

        gateway = raw.get("gateway") or {}
        if not isinstance(gateway, dict):
            raise ValueError("config: 'gateway' must be a mapping with url/api_key")
        url = str(gateway.get("url") or "").strip()
        api_key = str(gateway.get("api_key") or "").strip()
        if not url or not api_key:
            raise ValueError("config: gateway.url and gateway.api_key are required")

        watch = raw.get("watch") or list(DEFAULT_WATCH_PATHS)
        if not isinstance(watch, list) or not all(isinstance(p, str) for p in watch):
            raise ValueError("config: 'watch' must be a list of paths")

        policies_raw = raw.get("snapshot_policies") or []
        policies: list[dict[str, str]] = []
        for entry in policies_raw:
            if isinstance(entry, dict) and entry.get("path"):
                policies.append({
                    "path": str(entry["path"]),
                    "snapshot": str(entry.get("snapshot") or "full"),
                })

        return cls(
            gateway_url=url,
            api_key=api_key,
            node_hostname=str(raw.get("node_hostname") or socket.gethostname()),
            watch_paths=[str(p) for p in watch],
            snapshot_policies=policies,
            verify_tls=bool(gateway.get("verify_tls", False)),
            debounce_seconds=float(raw.get("debounce_seconds") or DEBOUNCE_SECONDS),
            heartbeat_interval_seconds=float(
                raw.get("heartbeat_interval_seconds") or HEARTBEAT_INTERVAL_SECONDS
            ),
            poll_interval_seconds=float(
                raw.get("poll_interval_seconds") or POLL_INTERVAL_SECONDS
            ),
            spool_dir=str(raw.get("spool_dir") or "/var/spool/compliance-agent"),
            state_dir=str(raw.get("state_dir") or "/var/lib/compliance-agent"),
            max_content_bytes=int(raw.get("max_content_bytes") or MAX_CONTENT_BYTES),
        )


# ── Snapshot policy (full vs hash-only) ───────────────────────────────────────

class SnapshotPolicy:
    """Decides, per path, whether the file CONTENT may be shipped to the
    gateway (``full``) or only its hash + metadata (``hash-only``).

    Explicit config rules win (longest matching path prefix / exact glob);
    otherwise the built-in private-material defaults apply: /etc/shadow, and
    any basename matching *key*, *.pem or *.crt stays hash-only. Everything
    else is full.
    """

    FULL = "full"
    HASH_ONLY = "hash-only"

    def __init__(self, rules: Optional[list[dict[str, str]]] = None) -> None:
        self._rules: list[tuple[str, str]] = []
        for entry in rules or []:
            mode = entry.get("snapshot", self.FULL)
            if mode not in (self.FULL, self.HASH_ONLY):
                mode = self.FULL
            self._rules.append((entry["path"], mode))

    def resolve(self, path: str) -> str:
        norm = os.path.normpath(path)

        # 1) explicit config rules — most specific (longest) match wins
        best: Optional[tuple[int, str]] = None
        for rule_path, mode in self._rules:
            rule_norm = os.path.normpath(rule_path)
            matched = (
                norm == rule_norm
                or norm.startswith(rule_norm + os.sep)
                or fnmatch.fnmatch(norm, rule_norm)
                or fnmatch.fnmatch(os.path.basename(norm), rule_path)
            )
            if matched and (best is None or len(rule_norm) > best[0]):
                best = (len(rule_norm), mode)
        if best is not None:
            return best[1]

        # 2) built-in private-material defaults
        if norm in DEFAULT_HASH_ONLY_PATHS:
            return self.HASH_ONLY
        base = os.path.basename(norm).lower()
        for pattern in DEFAULT_HASH_ONLY_BASENAME_GLOBS:
            if fnmatch.fnmatch(base, pattern):
                return self.HASH_ONLY

        return self.FULL


# ── Debouncer ────────────────────────────────────────────────────────────────

class Debouncer:
    """Collapses rapid successive events on the same path.

    An event is released only once the path has been quiet for ``window``
    seconds; further events within the window reset the timer and overwrite
    the pending event type (the final state is what gets snapshotted anyway).
    Thread-safe: watchdog observer threads call :meth:`offer`, the main loop
    calls :meth:`pop_due`. The clock is injectable for deterministic tests.
    """

    def __init__(self, window: float = DEBOUNCE_SECONDS,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.window = window
        self._clock = clock
        self._pending: dict[str, tuple[float, str]] = {}  # path -> (last_seen, event_type)
        self._lock = threading.Lock()

    def offer(self, path: str, event_type: str) -> None:
        with self._lock:
            self._pending[path] = (self._clock(), event_type)

    def pop_due(self) -> list[tuple[str, str]]:
        """Return [(path, event_type)] for every path quiet for >= window."""
        now = self._clock()
        due: list[tuple[str, str]] = []
        with self._lock:
            for path, (last_seen, event_type) in list(self._pending.items()):
                if now - last_seen >= self.window:
                    due.append((path, event_type))
                    del self._pending[path]
        return due

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)


# ── Snapshot / hashing ────────────────────────────────────────────────────────

@dataclass
class Snapshot:
    sha256: Optional[str]
    meta: Optional[dict[str, Any]]
    content: Optional[bytes]
    truncated: bool = False


def take_snapshot(path: str, want_content: bool, max_bytes: int = MAX_CONTENT_BYTES) -> Snapshot:
    """Read the file's current state. Missing file → all-None snapshot."""
    try:
        st = os.stat(path, follow_symlinks=False)
    except (FileNotFoundError, NotADirectoryError):
        return Snapshot(sha256=None, meta=None, content=None)
    except OSError as exc:
        logger.warning("stat(%s) failed: %s", path, exc)
        return Snapshot(sha256=None, meta=None, content=None)

    meta = {
        "mode": oct(st.st_mode & 0o7777),
        "uid": st.st_uid,
        "gid": st.st_gid,
        "size": st.st_size,
        "mtime": st.st_mtime,
    }

    hasher = hashlib.sha256()
    content = bytearray()
    truncated = False
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                hasher.update(chunk)
                if want_content and not truncated:
                    if len(content) + len(chunk) <= max_bytes:
                        content.extend(chunk)
                    else:
                        truncated = True
                        content.clear()
    except OSError as exc:
        logger.warning("read(%s) failed: %s", path, exc)
        return Snapshot(sha256=None, meta=meta, content=None)

    return Snapshot(
        sha256=hasher.hexdigest(),
        meta=meta,
        content=bytes(content) if (want_content and not truncated) else None,
        truncated=truncated,
    )


# ── Hash cache (prev_hash per path) ───────────────────────────────────────────

class HashCache:
    """Last-known SHA-256 per watched path, persisted as JSON so prev_hash
    survives agent restarts."""

    def __init__(self, state_dir: str) -> None:
        self._path = os.path.join(state_dir, "hashes.json")
        self._data: dict[str, str] = {}
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self._data = {str(k): str(v) for k, v in loaded.items()}
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            logger.warning("hash cache unreadable (%s) — starting fresh", exc)

    def get(self, path: str) -> Optional[str]:
        return self._data.get(path)

    def known(self, path: str) -> bool:
        return path in self._data

    def update(self, path: str, sha256: Optional[str]) -> None:
        if sha256 is None:
            self._data.pop(path, None)
        else:
            self._data[path] = sha256
        self._save()

    def _save(self) -> None:
        tmp = self._path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh)
            os.replace(tmp, self._path)
        except OSError as exc:
            logger.warning("hash cache save failed: %s", exc)


# ── Puppet-run guard ──────────────────────────────────────────────────────────

def puppet_running(lock_file: str = PUPPET_LOCK_FILE) -> bool:
    """True while Puppet's agent run lock exists. Never suppresses locally —
    the flag rides along on every event and the gateway decides."""
    return os.path.exists(lock_file)


# ── Actor enrichment via auditd (best effort) ─────────────────────────────────

_AUSEARCH_FIELDS = {
    "auid": re.compile(r"\bauid=(\d+)"),
    "uid": re.compile(r"\buid=(\d+)"),
    "exe": re.compile(r'\bexe="([^"]*)"'),
    "comm": re.compile(r'\bcomm="([^"]*)"'),
}
# auid is the login uid; unset (daemons, no login session) is -1 as a u32.
_AUID_UNSET = 4294967295


def _resolve_username(uid: Any) -> Optional[str]:
    """Map a numeric uid to a login name, or None. Isolated so the actor
    lookup degrades cleanly on non-Unix hosts (no ``pwd``) or unknown uids."""
    if not isinstance(uid, int) or uid < 0 or uid == _AUID_UNSET:
        return None
    try:
        import pwd  # Unix-only; imported lazily so the module loads anywhere.

        return pwd.getpwuid(uid).pw_name
    except (KeyError, ImportError, OverflowError, OSError):
        return None


def lookup_actor(path: str, timeout: float = 3.0) -> Optional[dict[str, Any]]:
    """Ask auditd (ausearch) who last wrote to *path*.

    Returns the most recent matching write's actor — ``{auid, uid, exe, comm,
    username}`` — where ``username`` resolves the login uid (falling back to
    the effective uid) to a human name so the evidence trail records *who*, not
    just a number. Returns None when auditd/ausearch is unavailable or has
    nothing. auditd is explicitly NOT a dependency — every failure path
    degrades to None.
    """
    try:
        proc = subprocess.run(
            ["ausearch", "-f", path, "--raw", "-ts", "recent"],
            capture_output=True, text=True, timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None

    actor: dict[str, Any] = {}
    # Scan from the end: the last SYSCALL record is the most recent write.
    for line in reversed(proc.stdout.splitlines()):
        for key, rx in _AUSEARCH_FIELDS.items():
            if key not in actor:
                m = rx.search(line)
                if m:
                    actor[key] = int(m.group(1)) if key in ("auid", "uid") else m.group(1)
        if len(actor) == len(_AUSEARCH_FIELDS):
            break
    if not actor:
        return None

    # Prefer the login uid (who logged in) over the effective uid (who the
    # process ran as, e.g. after sudo) when naming the human responsible.
    username = _resolve_username(actor.get("auid"))
    if username is None:
        username = _resolve_username(actor.get("uid"))
    if username is not None:
        actor["username"] = username
    return actor


# ── Gateway sender with retry + spool ─────────────────────────────────────────

class GatewaySender:
    """POSTs events to the gateway; retries with exponential backoff and spools
    to disk while the gateway is unreachable, flushing FIFO on reconnect."""

    def __init__(self, url: str, api_key: str, spool_dir: str,
                 verify_tls: bool = False, max_attempts: int = MAX_SEND_ATTEMPTS,
                 backoff_base: float = BACKOFF_BASE_SECONDS,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._url = url
        self._api_key = api_key
        self._spool_path = os.path.join(spool_dir, "events.spool")
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._sleep = sleep
        if verify_tls:
            self._ssl_ctx = ssl.create_default_context()
        else:
            # The platform ships with a self-signed certificate by default.
            self._ssl_ctx = ssl._create_unverified_context()  # noqa: SLF001

    # -- low-level single POST --
    def _post_once(self, payload: dict[str, Any]) -> bool:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._url,
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": self._api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15, context=self._ssl_ctx) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as exc:
            # 4xx = the gateway made a decision (bad key, unknown node…):
            # retrying the same payload cannot help, and spooling it would jam
            # the queue forever. Log loudly and drop.
            logger.error("gateway rejected event (HTTP %s): %s", exc.code, exc.reason)
            return exc.code < 500  # 4xx → treat as delivered-and-rejected
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            logger.warning("gateway unreachable: %s", exc)
            return False

    def send(self, payload: dict[str, Any]) -> bool:
        """Send with retry; on final failure append to the spool. Returns True
        when the payload was delivered (or definitively rejected)."""
        for attempt in range(self._max_attempts):
            if self._post_once(payload):
                if attempt:
                    logger.info("event delivered after %d retries", attempt)
                self.flush_spool()
                return True
            if attempt < self._max_attempts - 1:
                self._sleep(self._backoff_base * (2 ** attempt))
        self._spool(payload)
        return False

    # -- spool --
    def _spool(self, payload: dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(self._spool_path), exist_ok=True)
            with open(self._spool_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload) + "\n")
            logger.info("event spooled (gateway unreachable): %s", payload.get("path"))
        except OSError as exc:
            logger.error("spool write failed — event LOST: %s", exc)

    def spool_size(self) -> int:
        try:
            with open(self._spool_path, "r", encoding="utf-8") as fh:
                return sum(1 for line in fh if line.strip())
        except OSError:
            return 0

    def flush_spool(self) -> int:
        """Drain the spool FIFO. Stops at the first delivery failure so order
        is preserved. Returns the number of events flushed."""
        try:
            with open(self._spool_path, "r", encoding="utf-8") as fh:
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        except OSError:
            return 0
        if not lines:
            return 0

        flushed = 0
        for i, line in enumerate(lines):
            try:
                payload = json.loads(line)
            except ValueError:
                flushed += 1  # corrupt line — drop it
                continue
            if self._post_once(payload):
                flushed += 1
            else:
                break

        remaining = lines[flushed:]
        try:
            tmp = self._spool_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                for line in remaining:
                    fh.write(line + "\n")
            os.replace(tmp, self._spool_path)
        except OSError as exc:
            logger.error("spool rewrite failed: %s", exc)
        if flushed:
            logger.info("flushed %d spooled event(s), %d remaining", flushed, len(remaining))
        return flushed


# ── Event pipeline ────────────────────────────────────────────────────────────

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventPipeline:
    """Turns a debounced (path, event_type) into a gateway payload and sends it."""

    def __init__(self, config: AgentConfig, policy: SnapshotPolicy,
                 cache: HashCache, sender: GatewaySender,
                 actor_lookup: Callable[[str], Optional[dict[str, Any]]] = lookup_actor,
                 puppet_check: Callable[[], bool] = puppet_running) -> None:
        self._config = config
        self._policy = policy
        self._cache = cache
        self._sender = sender
        self._actor_lookup = actor_lookup
        self._puppet_check = puppet_check

    def build_payload(self, path: str, event_type: str) -> Optional[dict[str, Any]]:
        policy = self._policy.resolve(path)
        snap = take_snapshot(
            path, want_content=(policy == SnapshotPolicy.FULL),
            max_bytes=self._config.max_content_bytes,
        )
        prev_hash = self._cache.get(path)

        if snap.sha256 is None and event_type not in ("deleted", "moved"):
            # File vanished between the event and the snapshot → it's a delete.
            event_type = "deleted"
        if snap.sha256 is not None and event_type == "deleted":
            # Recreated during the debounce window → it's a modify.
            event_type = "modified"

        if snap.sha256 == prev_hash and event_type not in ("baseline",):
            # Content did not actually change (e.g. touch, or modify+revert
            # within the debounce window) — metadata-only changes still matter
            # for sudoers/shadow, but without a hash delta we skip to avoid
            # noise. The baseline event is always sent.
            logger.debug("skip %s: hash unchanged (%s)", path, event_type)
            return None

        payload: dict[str, Any] = {
            "node_hostname": self._config.node_hostname,
            "path": path,
            "event_type": event_type,
            "timestamp": utc_now_iso(),
            "prev_hash": prev_hash,
            "new_hash": snap.sha256,
            "file_meta": snap.meta,
            "puppet_running": self._puppet_check(),
            "actor": self._actor_lookup(path),
        }
        if snap.content is not None:
            payload["content_b64"] = base64.b64encode(snap.content).decode("ascii")
        if snap.truncated:
            payload["content_truncated"] = True
        return payload

    def process(self, path: str, event_type: str) -> None:
        payload = self.build_payload(path, event_type)
        if payload is None:
            return
        self._cache.update(path, payload["new_hash"])
        self._sender.send(payload)
        logger.info("event %s %s (prev=%s new=%s)", event_type, path,
                    (payload["prev_hash"] or "-")[:12], (payload["new_hash"] or "-")[:12])

    def heartbeat(self) -> None:
        self._sender.send({
            "node_hostname": self._config.node_hostname,
            "path": "",
            "event_type": "heartbeat",
            "timestamp": utc_now_iso(),
            "prev_hash": None,
            "new_hash": None,
            "file_meta": None,
            "puppet_running": self._puppet_check(),
            "actor": None,
        })
        logger.debug("heartbeat sent")

    # -- baseline --
    def _iter_watched_files(self) -> Iterator[str]:
        for root in self._config.watch_paths:
            root = os.path.normpath(root)
            if os.path.isfile(root):
                yield root
            elif os.path.isdir(root):
                for dirpath, _dirnames, filenames in os.walk(root):
                    for name in filenames:
                        yield os.path.join(dirpath, name)

    def baseline(self) -> int:
        """Snapshot every watched file that the cache has never seen.

        Runs at first start (and picks up newly-watched paths on restart).
        Baseline events carry event_type="baseline" so the gateway stores them
        as evidence without triggering remediation.
        """
        count = 0
        for path in self._iter_watched_files():
            if self._cache.known(path):
                continue
            self.process(path, "baseline")
            count += 1
        return count


# ── File-watch backends ───────────────────────────────────────────────────────
#
# Two interchangeable backends expose the SAME tiny contract — start(), stop(),
# join(timeout) and feeding debouncer.offer(path, event_type):
#
#   * watchdog (inotify) — event-driven, near-zero latency, preferred;
#   * _PollingWatcher (stdlib only) — a periodic stat sweep, used when watchdog
#     is not installed. This is what lets the agent run on ANY node with just
#     python3 (no pip, no distro package, airgap-safe) — the enforcement plane
#     must not be blocked by a missing optional dependency.


def _enumerate_targets(watch_paths: list[str]) -> tuple[list[str], dict[str, set[str]]]:
    """Split configured paths into recursive dir targets and per-parent exact
    file targets — shared by both backends so they watch identically."""
    file_targets: dict[str, set[str]] = {}   # parent dir -> exact file paths
    dir_targets: list[str] = []
    for raw in watch_paths:
        path = os.path.normpath(raw)
        if os.path.isdir(path):
            dir_targets.append(path)
        else:
            file_targets.setdefault(os.path.dirname(path) or "/", set()).add(path)
    return dir_targets, file_targets


class _PollingWatcher:
    """Stdlib-only fallback watcher: periodically stats every watched file and
    offers created/modified/deleted events when a path's signature
    (mtime_ns, size, inode) changes. Same offer() contract as the watchdog
    handlers, so everything downstream (debounce → pipeline → gateway) is
    identical. The first sweep seeds signatures WITHOUT emitting so a restart
    does not replay the whole watched tree as "modified"."""

    def __init__(self, config: AgentConfig, debouncer: Debouncer) -> None:
        self._debouncer = debouncer
        self._interval = max(1.0, float(config.poll_interval_seconds))
        self._dir_targets, self._file_targets = _enumerate_targets(config.watch_paths)
        self._sigs: dict[str, tuple] = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, name="sabc-poller", daemon=True)

    # watchdog-Observer-compatible surface -------------------------------------
    def start(self) -> None:
        self._sigs = self._scan()          # seed silently
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: Optional[float] = None) -> None:
        self._thread.join(timeout)

    # internals ----------------------------------------------------------------
    def _iter_paths(self) -> Iterator[str]:
        for d in self._dir_targets:
            for root, _dirs, files in os.walk(d):
                for name in files:
                    yield os.path.normpath(os.path.join(root, name))
        for parent, exact in self._file_targets.items():
            for p in exact:
                yield p

    def _scan(self) -> dict[str, tuple]:
        sigs: dict[str, tuple] = {}
        for p in self._iter_paths():
            try:
                st = os.stat(p)
            except OSError:
                continue  # gone between walk and stat — handled as a deletion
            sigs[p] = (st.st_mtime_ns, st.st_size, st.st_ino)
        return sigs

    def _emit_changes(self, new: dict[str, tuple]) -> None:
        """Offer created/modified/deleted for the delta vs the last sweep, then
        adopt the new signatures as the baseline."""
        for path, sig in new.items():
            old = self._sigs.get(path)
            if old is None:
                self._debouncer.offer(path, "created")
            elif old != sig:
                self._debouncer.offer(path, "modified")
        for path in self._sigs.keys() - new.keys():
            self._debouncer.offer(path, "deleted")
        self._sigs = new

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                new = self._scan()
            except Exception:
                logger.exception("poll scan failed")
                continue
            self._emit_changes(new)


def _build_watcher(config: AgentConfig, debouncer: Debouncer):
    """Return the best available watcher: watchdog (inotify) if importable,
    otherwise the stdlib polling fallback. Logs which backend is in use."""
    try:
        import watchdog  # noqa: F401
    except ImportError:
        logger.warning(
            "the 'watchdog' library is not installed — falling back to stdlib "
            "polling every %.0fs (install python3-watchdog for inotify-speed "
            "detection)", max(1.0, float(config.poll_interval_seconds)),
        )
        return _PollingWatcher(config, debouncer)
    logger.info("using watchdog (inotify) file-change backend")
    return _build_observer(config, debouncer)


def _build_observer(config: AgentConfig, debouncer: Debouncer):
    """Set up watchdog watches for every configured path.

    Directories are watched recursively; single files are watched through
    their parent directory with an exact-path filter (this also catches the
    write-temp-then-rename pattern editors and vipw use).
    """
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    dir_targets, file_targets = _enumerate_targets(config.watch_paths)

    class Handler(FileSystemEventHandler):
        def __init__(self, exact: Optional[set[str]] = None) -> None:
            self._exact = exact  # None → accept everything under a watched dir

        def _accept(self, path: str) -> bool:
            return self._exact is None or os.path.normpath(path) in self._exact

        def on_created(self, event) -> None:
            if not event.is_directory and self._accept(event.src_path):
                debouncer.offer(os.path.normpath(event.src_path), "created")

        def on_modified(self, event) -> None:
            if not event.is_directory and self._accept(event.src_path):
                debouncer.offer(os.path.normpath(event.src_path), "modified")

        def on_deleted(self, event) -> None:
            if not event.is_directory and self._accept(event.src_path):
                debouncer.offer(os.path.normpath(event.src_path), "deleted")

        def on_moved(self, event) -> None:
            if event.is_directory:
                return
            # rename away = delete of src; rename in = modify of dest
            if self._accept(event.src_path):
                debouncer.offer(os.path.normpath(event.src_path), "deleted")
            if getattr(event, "dest_path", None) and self._accept(event.dest_path):
                debouncer.offer(os.path.normpath(event.dest_path), "modified")

    observer = Observer()
    for d in dir_targets:
        observer.schedule(Handler(None), d, recursive=True)
    for parent, exact in file_targets.items():
        if os.path.isdir(parent):
            observer.schedule(Handler(exact), parent, recursive=False)
        else:
            logger.warning("watch parent %s does not exist — skipping %s", parent, exact)
    return observer


# ── Main loop ─────────────────────────────────────────────────────────────────

def run(config: AgentConfig) -> None:
    os.makedirs(config.state_dir, exist_ok=True)
    os.makedirs(config.spool_dir, exist_ok=True)

    policy = SnapshotPolicy(config.snapshot_policies)
    cache = HashCache(config.state_dir)
    sender = GatewaySender(
        config.gateway_url, config.api_key, config.spool_dir,
        verify_tls=config.verify_tls,
    )
    pipeline = EventPipeline(config, policy, cache, sender)
    debouncer = Debouncer(window=config.debounce_seconds)

    stop = threading.Event()

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("signal %s received — shutting down", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    observer = _build_watcher(config, debouncer)
    observer.start()
    logger.info(
        "watching %d path(s) for %s → %s",
        len(config.watch_paths), config.node_hostname, config.gateway_url,
    )

    n = pipeline.baseline()
    if n:
        logger.info("baseline snapshot complete: %d file(s)", n)

    last_heartbeat = time.monotonic()
    pipeline.heartbeat()  # announce liveness immediately after (re)start

    try:
        while not stop.is_set():
            for path, event_type in debouncer.pop_due():
                try:
                    pipeline.process(path, event_type)
                except Exception:  # one bad file must not kill the daemon
                    logger.exception("failed to process %s", path)

            now = time.monotonic()
            if now - last_heartbeat >= config.heartbeat_interval_seconds:
                last_heartbeat = now
                try:
                    pipeline.heartbeat()
                except Exception:
                    logger.exception("heartbeat failed")

            if sender.spool_size() and int(now) % 30 == 0:
                sender.flush_spool()

            stop.wait(0.5)
    finally:
        observer.stop()
        observer.join(timeout=5)
        logger.info("stopped")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SABC compliance detection agent")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH,
                        help=f"path to config.yaml (default: {DEFAULT_CONFIG_PATH})")
    parser.add_argument("--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        config = AgentConfig.load(args.config)
    except (OSError, ValueError) as exc:
        logger.error("cannot load config %s: %s", args.config, exc)
        return 2

    # watchdog is optional: run() selects the inotify backend when it is
    # importable and transparently falls back to stdlib polling otherwise, so a
    # missing optional dependency never stops the agent from starting.
    run(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
