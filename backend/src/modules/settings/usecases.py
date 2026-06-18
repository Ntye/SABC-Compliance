from __future__ import annotations
import asyncio
import base64
import logging
import os
import uuid
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


class DistributeCertificateUseCase:
    """Push the platform's server.crt to every registered node's OS trust store.

    Each node receives the certificate over SSH (as the ansible user with sudo)
    and the appropriate trust-store tool (update-ca-certificates on Debian/Ubuntu,
    update-ca-trust on RHEL/Rocky) installs it. Progress is streamed to a Job
    so the operator can watch it in real time via WebSocket.
    """

    def __init__(
        self,
        node_repo,
        job_repo,
        ws_manager,
        certs_dir: str,
        ssh_key_path: str,
    ) -> None:
        self._node_repo = node_repo
        self._job_repo = job_repo
        self._ws = ws_manager
        self._certs_dir = certs_dir
        self._ssh_key_path = ssh_key_path

    async def execute(self):
        """Create a cert_propagation Job, fire the background task, return the Job."""
        from core.domain.entities import Job as _Job
        now = datetime.utcnow()
        job = _Job(
            id=str(uuid.uuid4()),
            type="cert_propagation",
            status="pending",
            node_id=None,
            target_group="all",
            playbook="cert_propagation",
            created_at=now,
            updated_at=now,
        )
        await self._job_repo.save(job)
        asyncio.create_task(self._run(job))
        return job

    async def _run(self, job) -> None:
        from core.domain.entities import Job as _Job  # noqa: F401 (type hint)

        async def on_line(msg: str, level: str = "info") -> None:
            entry = {"ts": datetime.utcnow().isoformat(), "level": level, "line": msg}
            await self._job_repo.append_log(job.id, entry)
            await self._ws.broadcast(job.id, entry)

        job.start()
        await self._job_repo.update(job)

        # Read the certificate
        crt_path = os.path.join(self._certs_dir, "server.crt")
        try:
            with open(crt_path, "r") as fh:
                cert_pem = fh.read()
        except FileNotFoundError:
            await on_line(f"ERROR: Certificate not found at {crt_path}", "error")
            job.fail(1)
            job.updated_at = datetime.utcnow()
            await self._job_repo.update(job)
            done_entry = {
                "ts": datetime.utcnow().isoformat(),
                "level": "system",
                "line": f"── Job {job.status.upper()} (exit {job.exit_code}) ──",
            }
            await self._job_repo.append_log(job.id, done_entry)
            await self._ws.broadcast(job.id, done_entry)
            return

        # List nodes
        nodes = await self._node_repo.find_all({})
        await on_line(f"Propagating certificate to {len(nodes)} node(s) ...")

        if not nodes:
            await on_line("No registered nodes — nothing to do.")
            job.succeed(0)
            job.updated_at = datetime.utcnow()
            await self._job_repo.update(job)
            done_entry = {
                "ts": datetime.utcnow().isoformat(),
                "level": "system",
                "line": f"── Job {job.status.upper()} (exit {job.exit_code}) ──",
            }
            await self._job_repo.append_log(job.id, done_entry)
            await self._ws.broadcast(job.id, done_entry)
            return

        any_failed = False
        for node in nodes:
            ok = await self._push_to_node(node, cert_pem, on_line)
            tag = "[OK]" if ok else "[FAIL]"
            level = "info" if ok else "error"
            await on_line(f"{tag} {node.hostname} ({node.ip})", level)
            if not ok:
                any_failed = True

        if any_failed:
            job.fail(1)
        else:
            job.succeed(0)

        job.updated_at = datetime.utcnow()
        await self._job_repo.update(job)

        done_entry = {
            "ts": datetime.utcnow().isoformat(),
            "level": "system",
            "line": f"── Job {job.status.upper()} (exit {job.exit_code}) ──",
        }
        await self._job_repo.append_log(job.id, done_entry)
        await self._ws.broadcast(job.id, done_entry)

    async def _push_to_node(self, node, cert_pem: str, on_line) -> bool:
        """SSH into node and install the certificate into its OS trust store."""
        ssh_key = node.ssh_key_path or self._ssh_key_path

        # Base64-encode the cert to avoid heredoc quoting issues
        cert_b64 = base64.b64encode(cert_pem.encode()).decode()

        script = f"""#!/bin/bash
set -e
echo '{cert_b64}' | base64 -d > /tmp/sabc-platform.crt
if command -v update-ca-certificates >/dev/null 2>&1; then
  install -m 0644 /tmp/sabc-platform.crt /usr/local/share/ca-certificates/sabc-platform.crt
  update-ca-certificates
elif command -v update-ca-trust >/dev/null 2>&1; then
  install -m 0644 /tmp/sabc-platform.crt /etc/pki/ca-trust/source/anchors/sabc-platform.crt
  update-ca-trust extract
else
  rm -f /tmp/sabc-platform.crt
  echo "Unrecognised trust store" >&2
  exit 1
fi
rm -f /tmp/sabc-platform.crt
"""
        script_bytes = script.encode()

        cmd = [
            "ssh",
            "-i", ssh_key,
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=15",
            "-o", "BatchMode=yes",
            "-p", str(node.ssh_port),
            f"{node.ssh_user}@{node.ip}",
            "sudo bash -s",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(script_bytes), timeout=30.0)
            output = stdout.decode(errors="replace") if stdout else ""
            for line in output.splitlines():
                if line.strip():
                    await on_line(f"  {node.hostname}: {line}")
            return proc.returncode == 0
        except asyncio.TimeoutError:
            logger.error("Timeout pushing cert to node %s (%s)", node.hostname, node.ip)
            await on_line(f"  {node.hostname}: timed out after 30s", "error")
            return False
        except Exception as exc:
            logger.error("Error pushing cert to node %s: %s", node.hostname, exc)
            await on_line(f"  {node.hostname}: {exc}", "error")
            return False
