from __future__ import annotations
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal
from core.errors import ValidationError
from interface.http.routes.auth import get_current_principal, require_admin

router = APIRouter(prefix="/settings", tags=["Settings"])

# ── Pydantic models ───────────────────────────────────────────────────────────

class CertificateInfo(BaseModel):
    installed: bool
    subject_cn: str | None = None
    issuer_cn: str | None = None
    self_signed: bool | None = None
    not_before: str | None = None
    not_after: str | None = None
    days_until_expiry: int | None = None
    expired: bool | None = None
    sans: list[str] = []
    parse_error: str | None = None
    propagation_job_id: str | None = None


# ── Dependency injection ──────────────────────────────────────────────────────

_tls_cert_uc = None
_distribute_cert_uc = None


def set_use_cases(tls_cert_uc=None, distribute_cert_uc=None) -> None:
    global _tls_cert_uc, _distribute_cert_uc
    _tls_cert_uc = tls_cert_uc
    _distribute_cert_uc = distribute_cert_uc


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/tls/certificate", response_model=CertificateInfo, summary="Get the installed TLS certificate")
async def get_tls_certificate(principal: AuthPrincipal = Depends(get_current_principal)):
    """Return metadata about the certificate the frontend currently serves
    (subject, issuer, validity window, SANs, and whether it is self-signed)."""
    if _tls_cert_uc is None:
        raise HTTPException(status_code=503, detail="TLS certificate management not available")
    return CertificateInfo(**(await _tls_cert_uc.get_current()))


@router.post("/tls/certificate", response_model=CertificateInfo, summary="Install a CA-signed TLS certificate")
async def install_tls_certificate(
    certificate: UploadFile = File(..., description="PEM certificate (server.crt); include the full chain if your CA provides intermediates"),
    private_key: UploadFile = File(..., description="PEM private key (server.key), unencrypted"),
    principal: AuthPrincipal = Depends(require_admin),
):
    """Validate and install a CA-signed certificate + key for the frontend.

    The pair is checked (valid PEM, key matches cert, not expired) before
    anything is written — a bad upload cannot break the running frontend. On
    success the frontend reloads nginx automatically and HTTPS uses the new
    certificate within a few seconds, with no container restart.
    """
    if _tls_cert_uc is None:
        raise HTTPException(status_code=503, detail="TLS certificate management not available")
    cert_pem = await certificate.read()
    key_pem = await private_key.read()
    if not cert_pem or not key_pem:
        raise HTTPException(status_code=422, detail="Both a certificate and a private key file are required")
    try:
        info = await _tls_cert_uc.install(cert_pem, key_pem)
        if _distribute_cert_uc is not None:
            job = await _distribute_cert_uc.execute()
            info["propagation_job_id"] = job.id
        return CertificateInfo(**info)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/tls/certificate/propagate", summary="Push the platform certificate to all registered nodes")
async def propagate_tls_certificate(principal: AuthPrincipal = Depends(require_admin)):
    """Manually trigger propagation of the currently installed platform TLS certificate
    to every registered node's OS trust store. Returns a job ID for log streaming."""
    if _distribute_cert_uc is None:
        raise HTTPException(status_code=503, detail="Certificate distribution not available")
    job = await _distribute_cert_uc.execute()
    return {"job_id": job.id}
