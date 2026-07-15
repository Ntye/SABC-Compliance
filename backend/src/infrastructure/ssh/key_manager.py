"""
Filesystem management of the platform's Ansible SSH keypair, for rotation.

The keypair lives at ``key_path`` (private) / ``key_path.pub`` (public). Rotation
uses three well-known siblings so the process is crash-safe and resumable:

    {key_path}            active private key (what SSH uses)
    {key_path}.pub        active public key (installed on nodes)
    {key_path}.pending    a freshly generated key, not yet promoted
    {key_path}.prev       the immediately-previous active key, kept as a
                          fallback SSH identity so a node that hasn't been
                          cleaned up yet is never locked out

Promotion is an atomic rename dance (``os.replace``), so a restart mid-rotation
leaves a consistent active key. This module never touches remote nodes — that is
the rotation use case's job; here we only manage local key material.
"""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class SshKeyManager:
    def __init__(self, key_path: str, key_type: str = "ed25519") -> None:
        self._path = key_path
        self._type = key_type

    # ── Well-known paths ───────────────────────────────────────────────────────
    @property
    def path(self) -> str:
        return self._path

    @property
    def pub_path(self) -> str:
        return f"{self._path}.pub"

    @property
    def pending_path(self) -> str:
        return f"{self._path}.pending"

    @property
    def pending_pub_path(self) -> str:
        return f"{self._path}.pending.pub"

    @property
    def prev_path(self) -> str:
        return f"{self._path}.prev"

    @property
    def prev_pub_path(self) -> str:
        return f"{self._path}.prev.pub"

    # ── Reads ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _read(path: str) -> str | None:
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError:
            return None

    def read_public_key(self) -> str | None:
        return self._read(self.pub_path)

    def read_pending_public_key(self) -> str | None:
        return self._read(self.pending_pub_path)

    def read_prev_public_key(self) -> str | None:
        return self._read(self.prev_pub_path)

    def has_active(self) -> bool:
        return os.path.exists(self._path)

    def has_prev(self) -> bool:
        return os.path.exists(self.prev_path)

    # ── ssh-keygen helpers ─────────────────────────────────────────────────────
    @staticmethod
    async def _run(*args: str) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")

    async def fingerprint(self, pub_path: str | None = None) -> dict | None:
        """SHA256 fingerprint + key type of a public key, or None if absent."""
        p = pub_path or self.pub_path
        if not os.path.exists(p):
            return None
        rc, out, _ = await self._run("ssh-keygen", "-lf", p)
        if rc != 0:
            return None
        # Format: "256 SHA256:<fp> <comment> (ED25519)"
        parts = out.strip().split()
        if len(parts) < 2:
            return {"fingerprint": out.strip(), "type": None, "bits": None}
        return {
            "bits": parts[0],
            "fingerprint": parts[1],
            "type": parts[-1].strip("()") if parts[-1].startswith("(") else None,
        }

    async def generate_pending(self, comment: str = "sabc-ansible") -> str:
        """Generate a fresh keypair into the .pending slot; return its public key."""
        self.discard_pending()
        parent = os.path.dirname(self.pending_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        rc, _, err = await self._run(
            "ssh-keygen", "-t", self._type, "-N", "", "-f", self.pending_path, "-C", comment,
        )
        if rc != 0:
            raise RuntimeError(f"ssh-keygen failed: {err.strip() or 'unknown error'}")
        os.chmod(self.pending_path, 0o600)
        pub = self.read_pending_public_key()
        if not pub:
            raise RuntimeError("pending public key was not produced")
        return pub

    # ── Atomic promotion / cleanup ─────────────────────────────────────────────
    def promote_pending(self) -> None:
        """active → prev (kept as fallback), pending → active. Atomic renames."""
        if not os.path.exists(self.pending_path):
            raise RuntimeError("no pending key to promote")
        if os.path.exists(self._path):
            os.replace(self._path, self.prev_path)
        if os.path.exists(self.pub_path):
            os.replace(self.pub_path, self.prev_pub_path)
        os.replace(self.pending_path, self._path)
        os.replace(self.pending_pub_path, self.pub_path)
        os.chmod(self._path, 0o600)

    def discard_pending(self) -> None:
        for p in (self.pending_path, self.pending_pub_path):
            try:
                os.remove(p)
            except OSError:
                pass

    def drop_prev(self) -> None:
        """Retire the previous key once every node is confirmed off it."""
        for p in (self.prev_path, self.prev_pub_path):
            try:
                os.remove(p)
            except OSError:
                pass
