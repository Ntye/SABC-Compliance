"""Shared SSH host-key verification options.

Every place the platform shells out to ``ssh`` (the SSH adapter, provisioning,
the trust-store push, Ansible) must agree on how host keys are verified — so
the learned keys live in one file and a swapped key is caught everywhere.

We use ``StrictHostKeyChecking=accept-new`` (trust-on-first-use): OpenSSH adds
an unknown host's key on first contact, but **refuses to connect if a known
host's key later changes** — exactly the man-in-the-middle / key-swap case the
old ``StrictHostKeyChecking=no`` + ``/dev/null`` combination silently accepted.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def known_hosts_path(default_key_path: str | None) -> str:
    """A single, persistent known_hosts file shared by all SSH call sites.

    Placed alongside the platform's SSH key so it lives on the same persistent
    volume; overridable with ``SABC_KNOWN_HOSTS``.
    """
    override = os.environ.get("SABC_KNOWN_HOSTS")
    if override:
        return os.path.abspath(override)
    base = os.path.dirname(default_key_path) if default_key_path else ""
    if not base:
        base = "./keys"
    # Absolute so the SSH adapter, provisioning, the trust-store push and
    # Ansible (which runs from its own cwd) all point at the very same file.
    return os.path.abspath(os.path.join(base, "known_hosts"))


def host_key_opts(default_key_path: str | None) -> list[str]:
    """``-o`` arguments enabling TOFU host-key verification into a shared file."""
    kh = known_hosts_path(default_key_path)
    parent = os.path.dirname(kh)
    if parent:
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as exc:  # pragma: no cover - unusual FS error
            logger.warning("Could not create known_hosts dir %s: %s", parent, exc)
    return [
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"UserKnownHostsFile={kh}",
    ]
