"""Compliance profiles (referentials) — use cases.

A *profile* is a named collection of controls (a hardening referential). Two
referentials ship as built-in profiles, one per framework:

* **CIS Benchmark** (``framework="cis"``) — the pristine published standard.
  Immutable: read-only for every role. It is the canonical "original".
* **Internal Referential — SABC Linux** (``framework="internal"``) — SABC's own
  baseline, seeded from the same content but admin-editable and resettable back
  to the CIS original.

Both are seeded from ``seed_sabc_linux.json``. Admins can additionally create
custom profiles (``framework=None``) from the Custom Profiles page.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime

from core.domain.entities import (
    CIS_BENCHMARK_PROFILE_ID,
    INTERNAL_PROFILE_ID,
    Profile,
    ProfileControl,
)
from core.domain.interfaces import IProfileRepository

logger = logging.getLogger(__name__)

_SEED_FILE = os.path.join(os.path.dirname(__file__), "seed_sabc_linux.json")

# Editable control fields (everything except identity/ownership/timestamps).
_EDITABLE_FIELDS = {
    "section_id", "section", "title", "kind", "cis_id", "description",
    "recommended_value", "agreed_value", "risk_profile", "rationale",
    "validate_guideline", "configure_guideline", "regulatory", "notes",
    "check_command", "enabled", "position",
}


class ValidationError(Exception):
    """Raised when a request payload is invalid."""


class ProfileUseCases:
    def __init__(self, repo: IProfileRepository) -> None:
        self._repo = repo

    # ── seeding ───────────────────────────────────────────────────────────────
    @staticmethod
    def _controls_from_seed(seed_controls: list[dict], profile_id: str) -> list[ProfileControl]:
        """Materialise a fresh set of ProfileControl rows from raw seed dicts."""
        now = datetime.utcnow()
        controls: list[ProfileControl] = []
        for c in seed_controls:
            controls.append(ProfileControl(
                id=str(uuid.uuid4()),
                profile_id=profile_id,
                section_id=c.get("section_id") or "",
                section=c.get("section") or "General",
                title=c.get("title") or c.get("section_id") or "",
                position=c.get("position") or 0,
                kind=c.get("kind") or "control",
                cis_id=c.get("cis_id"),
                description=c.get("description"),
                recommended_value=c.get("recommended_value"),
                agreed_value=c.get("agreed_value"),
                risk_profile=c.get("risk_profile"),
                rationale=c.get("rationale"),
                validate_guideline=c.get("validate_guideline"),
                configure_guideline=c.get("configure_guideline"),
                regulatory=c.get("regulatory"),
                notes=c.get("notes"),
                check_command=c.get("check_command"),
                enabled=bool(c.get("enabled", True)),
                created_at=now,
                updated_at=now,
            ))
        return controls

    async def seed_builtin(self) -> None:
        """Seed the two built-in referentials on first boot (idempotent).

        Both the CIS Benchmark (immutable original) and the Internal Referential
        (admin-editable derivative) are seeded from the same bundled content.
        Each is only created if its ID is not already present, so edits to the
        internal referential are never overwritten on restart and the pristine
        CIS Benchmark keeps its original content.
        """
        if not os.path.isfile(_SEED_FILE):
            logger.warning("Profile seed file not found at %s — skipping seed", _SEED_FILE)
            return
        try:
            with open(_SEED_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to read profile seed file: %s", exc)
            return

        seed_controls = data.get("controls", [])
        os_family = data.get("os_family") or "linux"
        version = data.get("version") or "1.0.0"

        # 1. CIS Benchmark — the pristine, immutable original.
        if not await self._repo.find_by_id(CIS_BENCHMARK_PROFILE_ID):
            now = datetime.utcnow()
            cis = Profile(
                id=CIS_BENCHMARK_PROFILE_ID,
                name="CIS Benchmark",
                description=(
                    "Standard CIS Benchmark de durcissement Linux — référentiel "
                    "d'origine, en lecture seule. Sert de base canonique au "
                    "Référentiel interne SABC, qui peut y être réinitialisé."
                ),
                os_family=os_family,
                version=version,
                source="builtin",
                framework="cis",
                controls=self._controls_from_seed(seed_controls, CIS_BENCHMARK_PROFILE_ID),
                created_at=now,
                updated_at=now,
            )
            await self._repo.save(cis)
            logger.info("Seeded CIS Benchmark profile with %d controls", len(cis.controls))

        # 2. Internal Referential — SABC's editable baseline, derived from CIS.
        if not await self._repo.find_by_id(INTERNAL_PROFILE_ID):
            now = datetime.utcnow()
            internal = Profile(
                id=INTERNAL_PROFILE_ID,
                name=data.get("name") or "Référentiel Durcissement — SABC Linux",
                description=data.get("description"),
                os_family=os_family,
                version=version,
                source="builtin",
                framework="internal",
                controls=self._controls_from_seed(seed_controls, INTERNAL_PROFILE_ID),
                created_at=now,
                updated_at=now,
            )
            await self._repo.save(internal)
            logger.info("Seeded Internal Referential profile with %d controls", len(internal.controls))

    # ── profiles ────────────────────────────────────────────────────────────────
    async def list_profiles(self) -> list[Profile]:
        return await self._repo.find_all()

    async def get_profile(self, profile_id: str) -> Profile | None:
        return await self._repo.find_by_id(profile_id)

    async def create_profile(self, data: dict) -> Profile:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("Profile name is required.")
        now = datetime.utcnow()
        profile = Profile(
            id=str(uuid.uuid4()),
            name=name,
            description=(data.get("description") or None),
            os_family=(data.get("os_family") or "linux"),
            version=(data.get("version") or "1.0.0"),
            source="custom",
            controls=[],
            created_at=now,
            updated_at=now,
        )
        await self._repo.save(profile)
        return profile

    @staticmethod
    def _ensure_editable(profile: Profile) -> None:
        """Reject any write to the immutable CIS Benchmark original."""
        if profile.locked:
            raise ValidationError(
                "The CIS Benchmark is the read-only original referential and "
                "cannot be modified. Edit the Internal Referential instead."
            )

    async def update_profile(self, profile_id: str, data: dict) -> Profile:
        profile = await self._repo.find_by_id(profile_id)
        if not profile:
            raise ValidationError("Profile not found.")
        self._ensure_editable(profile)
        if "name" in data and data["name"] is not None:
            name = str(data["name"]).strip()
            if not name:
                raise ValidationError("Profile name cannot be empty.")
            profile.name = name
        for fld in ("description", "os_family", "version"):
            if fld in data and data[fld] is not None:
                setattr(profile, fld, data[fld] or None)
        profile.updated_at = datetime.utcnow()
        await self._repo.update(profile)
        return await self._repo.find_by_id(profile_id)

    async def delete_profile(self, profile_id: str) -> None:
        profile = await self._repo.find_by_id(profile_id)
        if not profile:
            raise ValidationError("Profile not found.")
        if profile.source == "builtin":
            raise ValidationError(
                "The built-in SABC referential cannot be deleted. "
                "Disable individual controls instead, or duplicate it into a custom profile."
            )
        await self._repo.delete(profile_id)

    # ── controls ──────────────────────────────────────────────────────────────
    async def add_control(self, profile_id: str, data: dict) -> ProfileControl:
        profile = await self._repo.find_by_id(profile_id)
        if not profile:
            raise ValidationError("Profile not found.")
        self._ensure_editable(profile)
        section_id = (data.get("section_id") or "").strip()
        title = (data.get("title") or "").strip()
        if not title:
            raise ValidationError("Control title is required.")
        now = datetime.utcnow()
        max_pos = max((c.position for c in profile.controls), default=0)
        control = ProfileControl(
            id=str(uuid.uuid4()),
            profile_id=profile_id,
            section_id=section_id or title,
            section=(data.get("section") or "General"),
            title=title,
            position=data.get("position") if data.get("position") is not None else max_pos + 1,
            kind=(data.get("kind") or "control"),
            cis_id=data.get("cis_id"),
            description=data.get("description"),
            recommended_value=data.get("recommended_value"),
            agreed_value=data.get("agreed_value"),
            risk_profile=data.get("risk_profile"),
            rationale=data.get("rationale"),
            validate_guideline=data.get("validate_guideline"),
            configure_guideline=data.get("configure_guideline"),
            regulatory=data.get("regulatory"),
            notes=data.get("notes"),
            check_command=data.get("check_command"),
            enabled=bool(data.get("enabled", True)),
            created_at=now,
            updated_at=now,
        )
        await self._repo.save_control(control)
        return control

    async def update_control(self, control_id: str, data: dict) -> ProfileControl:
        control = await self._repo.find_control(control_id)
        if not control:
            raise ValidationError("Control not found.")
        parent = await self._repo.find_by_id(control.profile_id)
        if parent:
            self._ensure_editable(parent)
        # Save a history snapshot before applying changes
        snapshot = json.dumps({
            "section_id": control.section_id, "section": control.section,
            "title": control.title, "kind": control.kind, "cis_id": control.cis_id,
            "description": control.description, "recommended_value": control.recommended_value,
            "agreed_value": control.agreed_value, "risk_profile": control.risk_profile,
            "rationale": control.rationale, "validate_guideline": control.validate_guideline,
            "configure_guideline": control.configure_guideline, "regulatory": control.regulatory,
            "notes": control.notes, "check_command": control.check_command,
            "enabled": control.enabled, "position": control.position,
        })
        await self._repo.save_control_history(control_id, snapshot)
        for fld in _EDITABLE_FIELDS:
            if fld in data and data[fld] is not None:
                if fld == "enabled":
                    control.enabled = bool(data[fld])
                elif fld == "position":
                    control.position = int(data[fld])
                else:
                    setattr(control, fld, data[fld])
        control.updated_at = datetime.utcnow()
        await self._repo.update_control(control)
        return await self._repo.find_control(control_id)

    async def get_control_history(self, control_id: str) -> list[dict]:
        return await self._repo.get_control_history(control_id)

    async def delete_control(self, control_id: str) -> None:
        control = await self._repo.find_control(control_id)
        if not control:
            raise ValidationError("Control not found.")
        parent = await self._repo.find_by_id(control.profile_id)
        if parent:
            self._ensure_editable(parent)
        await self._repo.delete_control(control_id)

    # ── revert ────────────────────────────────────────────────────────────────
    async def revert_to_original(self, profile_id: str) -> Profile:
        """Reset the Internal Referential's controls to the CIS Benchmark original.

        Every control of the target profile is discarded and replaced by a fresh
        copy of the pristine CIS Benchmark controls. Only the editable internal
        referential may be reverted; the CIS Benchmark itself is read-only and
        custom profiles have no "original" to revert to.
        """
        profile = await self._repo.find_by_id(profile_id)
        if not profile:
            raise ValidationError("Profile not found.")
        if profile.framework != "internal":
            raise ValidationError(
                "Only the Internal Referential can be reverted to the CIS "
                "Benchmark original."
            )
        cis = await self._repo.find_by_id(CIS_BENCHMARK_PROFILE_ID)
        if not cis:
            raise ValidationError("CIS Benchmark original not found — cannot revert.")

        now = datetime.utcnow()
        for c in profile.controls:
            await self._repo.delete_control(c.id)
        for src in cis.controls:
            clone = ProfileControl(
                id=str(uuid.uuid4()),
                profile_id=profile_id,
                section_id=src.section_id,
                section=src.section,
                title=src.title,
                position=src.position,
                kind=src.kind,
                cis_id=src.cis_id,
                description=src.description,
                recommended_value=src.recommended_value,
                agreed_value=src.agreed_value,
                risk_profile=src.risk_profile,
                rationale=src.rationale,
                validate_guideline=src.validate_guideline,
                configure_guideline=src.configure_guideline,
                regulatory=src.regulatory,
                notes=src.notes,
                check_command=src.check_command,
                enabled=src.enabled,
                created_at=now,
                updated_at=now,
            )
            await self._repo.save_control(clone)
        profile.updated_at = now
        await self._repo.update(profile)
        logger.info("Reverted profile '%s' to CIS Benchmark original (%d controls)",
                    profile_id, len(cis.controls))
        return await self._repo.find_by_id(profile_id)

    async def search_controls(self, query: str, limit: int = 40) -> list[ProfileControl]:
        """Search controls across all profiles — used by the reuse picker in the UI."""
        if not query or len(query.strip()) < 2:
            return []
        return await self._repo.search_controls(query.strip(), limit)
