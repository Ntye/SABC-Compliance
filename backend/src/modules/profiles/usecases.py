"""Compliance profiles (referentials) — use cases.

A *profile* is a named, editable collection of controls (a hardening
referential). The SABC Linux hardening referential ships as a built-in profile
seeded from ``seed_sabc_linux.json``; operators can edit its controls and create
additional custom profiles from the Custom Profiles page.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime

from core.domain.entities import Profile, ProfileControl
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
    async def seed_builtin(self) -> None:
        """Load the bundled SABC referential on first boot (idempotent).

        The built-in profile is only seeded if it is not already present, so
        operator edits to its controls are never overwritten on restart.
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

        pid = data.get("id") or "sabc-linux-baseline"
        if await self._repo.find_by_id(pid):
            return  # already seeded — preserve operator edits

        now = datetime.utcnow()
        controls: list[ProfileControl] = []
        for c in data.get("controls", []):
            controls.append(ProfileControl(
                id=str(uuid.uuid4()),
                profile_id=pid,
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
        profile = Profile(
            id=pid,
            name=data.get("name") or "SABC Linux Baseline",
            description=data.get("description"),
            os_family=data.get("os_family") or "linux",
            version=data.get("version") or "1.0.0",
            source="builtin",
            controls=controls,
            created_at=now,
            updated_at=now,
        )
        await self._repo.save(profile)
        logger.info("Seeded built-in profile '%s' with %d controls", pid, len(controls))

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

    async def update_profile(self, profile_id: str, data: dict) -> Profile:
        profile = await self._repo.find_by_id(profile_id)
        if not profile:
            raise ValidationError("Profile not found.")
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
        await self._repo.delete_control(control_id)

    async def search_controls(self, query: str, limit: int = 40) -> list[ProfileControl]:
        """Search controls across all profiles — used by the reuse picker in the UI."""
        if not query or len(query.strip()) < 2:
            return []
        return await self._repo.search_controls(query.strip(), limit)
