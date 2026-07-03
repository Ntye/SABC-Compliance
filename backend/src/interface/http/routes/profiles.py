from __future__ import annotations
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from core.domain.entities import AuthPrincipal, Profile, ProfileControl
from interface.http.routes.auth import get_current_principal, require_admin
from modules.profiles.usecases import ProfileUseCases, ValidationError

router = APIRouter(prefix="/profiles", tags=["Profiles"])

# ── Pydantic models ───────────────────────────────────────────────────────────

class ProfileCreateRequest(BaseModel):
    name: str
    description: str | None = None
    os_family: str | None = "linux"
    version: str | None = "1.0.0"


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    os_family: str | None = None
    version: str | None = None


class DuplicateRequest(BaseModel):
    name: str | None = None  # defaults to "<original name> (copy)"


class ControlRequest(BaseModel):
    section_id: str | None = None
    section: str | None = None
    title: str | None = None
    kind: str | None = None
    cis_id: str | None = None
    description: str | None = None
    recommended_value: str | None = None
    agreed_value: str | None = None
    risk_profile: str | None = None
    rationale: str | None = None
    validate_guideline: str | None = None
    configure_guideline: str | None = None
    regulatory: str | None = None
    notes: str | None = None
    check_command: str | None = None
    enabled: bool | None = None
    position: int | None = None


# ── Dependency injection (set by main.py) ─────────────────────────────────────

_uc: ProfileUseCases | None = None


def set_use_cases(uc: ProfileUseCases) -> None:
    global _uc
    _uc = uc


# ── Serialisation ──────────────────────────────────────────────────────────────

def _control_dict(c: ProfileControl) -> dict:
    return {
        "id": c.id,
        "profile_id": c.profile_id,
        "section_id": c.section_id,
        "section": c.section,
        "title": c.title,
        "position": c.position,
        "kind": c.kind,
        "cis_id": c.cis_id,
        "description": c.description,
        "recommended_value": c.recommended_value,
        "agreed_value": c.agreed_value,
        "risk_profile": c.risk_profile,
        "rationale": c.rationale,
        "validate_guideline": c.validate_guideline,
        "configure_guideline": c.configure_guideline,
        "regulatory": c.regulatory,
        "notes": c.notes,
        "check_command": c.check_command,
        "enabled": c.enabled,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _profile_summary(p: Profile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "os_family": p.os_family,
        "version": p.version,
        "source": p.source,
        "framework": p.framework,
        "locked": p.locked,
        "control_count": p.control_count,
        "section_count": p.section_count,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _profile_detail(p: Profile) -> dict:
    return {**_profile_summary(p), "controls": [_control_dict(c) for c in p.controls]}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", summary="List compliance profiles (referentials)")
async def list_profiles(principal: AuthPrincipal = Depends(get_current_principal)):
    profiles = await _uc.list_profiles()
    return [_profile_summary(p) for p in profiles]


@router.get("/-/controls", summary="Search controls across all profiles (reuse picker)")
async def search_controls(
    q: str = "",
    limit: int = 40,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    controls = await _uc.search_controls(q, min(limit, 100))
    return [_control_dict(c) for c in controls]


@router.get("/-/csv-template", summary="Download the CSV template for profile import")
async def csv_template(principal: AuthPrincipal = Depends(get_current_principal)):
    """Header + sample rows showing the expected columns. Edit it, then upload
    via *Import CSV* to create a new profile or update an existing one."""
    return PlainTextResponse(
        content=_uc.csv_template(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="profile-template.csv"'},
    )


@router.post("/-/import-csv", summary="Import a CSV to create or update a profile")
async def import_csv(
    file: UploadFile = File(..., description="CSV file (see /profiles/-/csv-template)"),
    profile_id: str | None = Form(None, description="Update this profile; omit to create a new one"),
    name: str | None = Form(None, description="New profile name (create mode)"),
    description: str | None = Form(None),
    os_family: str | None = Form(None),
    version: str | None = Form(None),
    principal: AuthPrincipal = Depends(require_admin),
):
    """
    Validation-first import: the whole file is checked (columns, kinds,
    positions, and duplicate controls within the file) and nothing is written
    unless it is fully valid — repeated controls are reported with their row
    numbers instead of being silently created twice.

    With ``profile_id``: rows are matched to existing controls by kind +
    section_id (fallback title); matches update fields (empty cells leave the
    current value unchanged, changes are recorded in control history), new rows
    are added, and controls absent from the CSV are left untouched.
    Without ``profile_id``: creates a new custom profile named ``name``.
    """
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="CSV file too large (max 5 MB).")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File must be UTF-8 encoded CSV.")
    try:
        return await _uc.import_profile_csv(
            text, profile_id=profile_id or None, name=name,
            description=description, os_family=os_family, version=version,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("", summary="Create a custom compliance profile")
async def create_profile(body: ProfileCreateRequest, principal: AuthPrincipal = Depends(require_admin)):
    try:
        p = await _uc.create_profile(body.model_dump(exclude_unset=True))
        return _profile_detail(p)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{profile_id}", summary="Profile detail with all controls")
async def get_profile(profile_id: str, principal: AuthPrincipal = Depends(get_current_principal)):
    p = await _uc.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return _profile_detail(p)


@router.patch("/{profile_id}", summary="Update profile metadata")
async def update_profile(profile_id: str, body: ProfileUpdateRequest, principal: AuthPrincipal = Depends(require_admin)):
    try:
        p = await _uc.update_profile(profile_id, body.model_dump(exclude_unset=True))
        return _profile_detail(p)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{profile_id}/duplicate", summary="Duplicate a profile into a new custom profile")
async def duplicate_profile(
    profile_id: str,
    body: DuplicateRequest | None = None,
    principal: AuthPrincipal = Depends(require_admin),
):
    """Clone any profile (including the read-only CIS Benchmark) into a fresh,
    fully editable custom profile with all its controls."""
    try:
        p = await _uc.duplicate_profile(profile_id, body.name if body else None)
        return _profile_detail(p)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{profile_id}/export.csv", summary="Export a profile's controls as CSV")
async def export_csv(profile_id: str, principal: AuthPrincipal = Depends(get_current_principal)):
    """Full CSV of the profile's controls — edit offline and re-upload via
    *Import CSV* to apply changes, or use it as the base for a new profile."""
    try:
        filename, content = await _uc.export_profile_csv(profile_id)
    except ValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return PlainTextResponse(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{profile_id}/revert", summary="Reset the Internal Referential to the CIS Benchmark original")
async def revert_profile(profile_id: str, principal: AuthPrincipal = Depends(require_admin)):
    try:
        p = await _uc.revert_to_original(profile_id)
        return _profile_detail(p)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{profile_id}", summary="Delete a custom profile")
async def delete_profile(profile_id: str, principal: AuthPrincipal = Depends(require_admin)):
    try:
        await _uc.delete_profile(profile_id)
        return {"deleted": True}
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{profile_id}/controls", summary="Add a control to a profile")
async def add_control(profile_id: str, body: ControlRequest, principal: AuthPrincipal = Depends(require_admin)):
    try:
        c = await _uc.add_control(profile_id, body.model_dump(exclude_unset=True))
        return _control_dict(c)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/{profile_id}/controls/{control_id}", summary="Edit a control")
async def update_control(profile_id: str, control_id: str, body: ControlRequest, principal: AuthPrincipal = Depends(require_admin)):
    try:
        c = await _uc.update_control(control_id, body.model_dump(exclude_unset=True))
        return _control_dict(c)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{profile_id}/controls/{control_id}", summary="Remove a control")
async def delete_control(profile_id: str, control_id: str, principal: AuthPrincipal = Depends(require_admin)):
    try:
        await _uc.delete_control(control_id)
        return {"deleted": True}
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{profile_id}/controls/{control_id}/history", summary="Control edit history")
async def get_control_history(
    profile_id: str, control_id: str,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    import json as _json
    entries = await _uc.get_control_history(control_id)
    return [
        {"id": e["id"], "saved_at": e["saved_at"], "snapshot": _json.loads(e["snapshot"])}
        for e in entries
    ]


@router.post("/{profile_id}/import-scan-controls", summary="Populate check_command from bundled CIS profile")
async def import_scan_commands(
    profile_id: str,
    principal: AuthPrincipal = Depends(require_admin),
):
    """
    Reads the bundled CIS .rb control files and writes the matching check
    snippet into check_command for every referential control that has an empty
    check_command.  Controls that already have a check_command are never
    overwritten — edit history ensures no data is lost.
    """
    from modules.profiles.scan_import import load_all_scan_controls, match_controls
    p = await _uc.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found.")

    scan_controls = load_all_scan_controls()
    seed_controls = [
        {"id": c.id, "cis_id": c.cis_id, "title": c.title}
        for c in p.controls
        if c.kind == "control" and not c.check_command
    ]
    mapping = match_controls(scan_controls, seed_controls)

    updated = 0
    for ctrl_id, code in mapping.items():
        await _uc.update_control(ctrl_id, {"check_command": code})
        updated += 1

    return {"updated": updated, "total_scan": len(scan_controls), "total_seed": len(seed_controls)}
