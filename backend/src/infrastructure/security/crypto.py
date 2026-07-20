"""Symmetric encryption for secrets at rest.

A small Fernet wrapper used to encrypt the handful of genuinely sensitive
values the platform persists (Puppet console password, detection-webhook key).
Design goals:

* **Transparent + backward-compatible.** Ciphertext carries a ``enc:v1:`` tag.
  ``decrypt`` returns any untagged value unchanged, so a database that still
  holds legacy plaintext keeps working and is upgraded in place on next write.
* **Key lives outside the database.** The master key comes from ``MASTER_KEY``
  (env) or a ``0600`` key file next to the DB — never from the same table it
  protects — so a leaked DB dump alone does not reveal the secrets.
* **Fail safe, not closed.** If a value cannot be decrypted (wrong/rotated
  key), ``decrypt`` returns it verbatim rather than raising, so one bad row
  never takes the service down.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"


def _fernet_from_secret(master: str) -> Fernet:
    # Derive a stable 32-byte urlsafe key from an arbitrary-length master secret.
    digest = hashlib.sha256(master.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class SecretBox:
    """Encrypt/decrypt short secret strings with a tagged, versioned format."""

    def __init__(self, master: str) -> None:
        if not master:
            raise ValueError("SecretBox requires a non-empty master secret")
        self._fernet = _fernet_from_secret(master)

    @staticmethod
    def is_encrypted(value: str | None) -> bool:
        return bool(value) and value.startswith(_PREFIX)

    def encrypt(self, plaintext: str | None) -> str | None:
        if plaintext is None or plaintext == "":
            return plaintext
        if self.is_encrypted(plaintext):
            return plaintext  # already encrypted — never double-wrap
        token = self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
        return _PREFIX + token

    def decrypt(self, value: str | None) -> str | None:
        if not self.is_encrypted(value):
            return value  # legacy plaintext or non-secret — pass through
        try:
            return self._fernet.decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError):
            # Wrong/rotated key: surface the stored value rather than crash.
            logger.warning("SecretBox could not decrypt a stored value (wrong master key?)")
            return value


def resolve_master_key(explicit: str | None, key_file: str) -> str:
    """Return the master secret, preferring an explicit env value.

    Falls back to a random key persisted (``0600``) at ``key_file`` so secrets
    stay decryptable across restarts without the operator having to set anything,
    while still keeping the key off the database.
    """
    if explicit and explicit.strip():
        return explicit.strip()

    try:
        if os.path.exists(key_file):
            with open(key_file, "r", encoding="utf-8") as fh:
                stored = fh.read().strip()
            if stored:
                return stored
    except OSError as exc:  # pragma: no cover - unusual FS error
        logger.warning("Could not read master key file %s: %s", key_file, exc)

    generated = secrets.token_urlsafe(48)
    try:
        parent = os.path.dirname(key_file)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # Write atomically-ish, then lock down permissions.
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(generated)
        os.chmod(key_file, 0o600)
        logger.warning(
            "No MASTER_KEY set; generated and persisted a random one at %s. "
            "Set MASTER_KEY in the environment for production so secrets stay "
            "portable across hosts.", key_file,
        )
    except OSError as exc:  # pragma: no cover - unusual FS error
        logger.warning("Could not persist master key file %s: %s", key_file, exc)
    return generated
