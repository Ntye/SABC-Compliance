from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.x509.oid import NameOID

from core.errors import ValidationError

logger = logging.getLogger(__name__)


def _common_name(name: x509.Name) -> str | None:
    """Return the CN attribute of an X.509 name, or None if absent."""
    try:
        attrs = name.get_attributes_for_oid(NameOID.COMMON_NAME)
        return attrs[0].value if attrs else None
    except Exception:
        return None


def _not_after(cert: x509.Certificate) -> datetime:
    """Expiry as a timezone-aware datetime, across cryptography versions."""
    # cryptography >= 42 exposes the tz-aware accessor; older versions return
    # a naive UTC datetime from the deprecated attribute.
    dt = getattr(cert, "not_valid_after_utc", None)
    if dt is None:
        dt = cert.not_valid_after.replace(tzinfo=timezone.utc)
    return dt


def _not_before(cert: x509.Certificate) -> datetime:
    dt = getattr(cert, "not_valid_before_utc", None)
    if dt is None:
        dt = cert.not_valid_before.replace(tzinfo=timezone.utc)
    return dt


def _sans(cert: x509.Certificate) -> list[str]:
    """Subject Alternative Names (DNS + IP), as a flat list of strings."""
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound:
        return []
    san = ext.value
    names = list(san.get_values_for_type(x509.DNSName))
    names += [str(ip) for ip in san.get_values_for_type(x509.IPAddress)]
    return names


def _describe(cert: x509.Certificate) -> dict[str, Any]:
    """Build a JSON-serialisable summary of a parsed certificate."""
    not_after = _not_after(cert)
    now = datetime.now(timezone.utc)
    days_left = (not_after - now).days
    subject_cn = _common_name(cert.subject)
    issuer_cn = _common_name(cert.issuer)
    self_signed = cert.issuer == cert.subject
    return {
        "subject_cn": subject_cn,
        "issuer_cn": issuer_cn,
        "self_signed": self_signed,
        "not_before": _not_before(cert).isoformat(),
        "not_after": not_after.isoformat(),
        "days_until_expiry": days_left,
        "expired": days_left < 0,
        "sans": _sans(cert),
    }


class TlsCertificateUseCase:
    """Install and inspect the platform's frontend TLS certificate.

    The cert/key live in a directory shared with the frontend container (the
    frontend-certs Docker volume).  The frontend entrypoint watches the cert
    file and reloads nginx automatically when it changes, so an uploaded
    CA-signed certificate takes effect with no container restart.
    """

    def __init__(self, certs_dir: str) -> None:
        self._certs_dir = certs_dir
        self._crt_path = os.path.join(certs_dir, "server.crt")
        self._key_path = os.path.join(certs_dir, "server.key")

    # ── Read current ──────────────────────────────────────────────────────────
    async def get_current(self) -> dict[str, Any]:
        """Return metadata about the currently installed certificate (if any)."""
        if not os.path.isfile(self._crt_path):
            return {"installed": False}
        try:
            with open(self._crt_path, "rb") as fh:
                cert = x509.load_pem_x509_certificate(fh.read())
        except Exception as exc:  # corrupt / unreadable cert on disk
            logger.warning("Could not parse installed certificate: %s", exc)
            return {"installed": True, "parse_error": str(exc)}
        info = _describe(cert)
        info["installed"] = True
        return info

    # ── Install new ─────────────────────────────────────────────────────────────
    async def install(self, cert_pem: bytes, key_pem: bytes) -> dict[str, Any]:
        """Validate a cert/key pair and atomically write it to the shared volume.

        Raises ValidationError with a human-readable message on any problem so
        the caller can surface it to the operator. Nothing is written unless
        both the certificate and the key parse AND the key matches the cert —
        a bad upload can never break the running frontend.
        """
        # 1) Parse the certificate
        try:
            cert = x509.load_pem_x509_certificate(cert_pem)
        except Exception as exc:
            raise ValidationError(f"Certificate is not valid PEM-encoded X.509: {exc}")

        # 2) Parse the private key (unencrypted PEM only — encrypted keys can't
        #    be served by nginx without a passphrase prompt)
        try:
            key = serialization.load_pem_private_key(key_pem, password=None)
        except TypeError:
            raise ValidationError(
                "Private key appears to be passphrase-protected. Decrypt it first: "
                "openssl rsa -in encrypted.key -out server.key"
            )
        except Exception as exc:
            raise ValidationError(f"Private key is not a valid unencrypted PEM key: {exc}")

        # 3) Confirm the key matches the certificate (compare public keys)
        try:
            cert_pub = cert.public_key().public_bytes(
                Encoding.DER, PublicFormat.SubjectPublicKeyInfo
            )
            key_pub = key.public_key().public_bytes(
                Encoding.DER, PublicFormat.SubjectPublicKeyInfo
            )
        except Exception as exc:
            raise ValidationError(f"Could not compare key and certificate: {exc}")
        if cert_pub != key_pub:
            raise ValidationError(
                "The private key does not match the certificate (public keys differ). "
                "Make sure you uploaded the key that was generated with this certificate."
            )

        # 4) Warn-worthy but not fatal: already expired
        info = _describe(cert)
        if info["expired"]:
            raise ValidationError(
                f"Certificate expired on {info['not_after']}. Upload a current certificate."
            )

        # 5) Atomic write — key first, then cert. The frontend watches the cert
        #    file; writing the key first guarantees it is already in place when
        #    the cert change triggers an nginx reload, so the pair is never
        #    momentarily mismatched.
        os.makedirs(self._certs_dir, exist_ok=True)
        self._atomic_write(self._key_path, key_pem, mode=0o600)
        self._atomic_write(self._crt_path, cert_pem, mode=0o644)

        logger.info(
            "Installed TLS certificate: subject=%s issuer=%s expires=%s",
            info["subject_cn"], info["issuer_cn"], info["not_after"],
        )
        info["installed"] = True
        return info

    @staticmethod
    def _atomic_write(path: str, data: bytes, mode: int) -> None:
        tmp = f"{path}.tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)  # atomic on the same filesystem
