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

    # ── duplicate ─────────────────────────────────────────────────────────────
    async def duplicate_profile(self, profile_id: str, new_name: str | None = None) -> Profile:
        """Clone any profile (builtin or custom) into a fresh CUSTOM profile.

        The copy is always ``source="custom", framework=None`` so it is freely
        editable and deletable regardless of the original's lock state — this is
        the sanctioned way to derive a working referential from the CIS original.
        Controls are cloned with new ids, preserving order and every field.
        """
        src = await self._repo.find_by_id(profile_id)
        if not src:
            raise ValidationError("Profile not found.")
        name = (new_name or "").strip() or f"{src.name} (copy)"
        existing_names = {p.name for p in await self._repo.find_all()}
        if name in existing_names:
            i = 2
            while f"{name} ({i})" in existing_names:
                i += 1
            name = f"{name} ({i})"

        now = datetime.utcnow()
        copy = Profile(
            id=str(uuid.uuid4()),
            name=name,
            description=src.description,
            os_family=src.os_family,
            version=src.version,
            source="custom",
            framework=None,
            controls=[],
            created_at=now,
            updated_at=now,
        )
        copy.controls = [
            ProfileControl(
                id=str(uuid.uuid4()),
                profile_id=copy.id,
                section_id=c.section_id, section=c.section, title=c.title,
                position=c.position, kind=c.kind, cis_id=c.cis_id,
                description=c.description, recommended_value=c.recommended_value,
                agreed_value=c.agreed_value, risk_profile=c.risk_profile,
                rationale=c.rationale, validate_guideline=c.validate_guideline,
                configure_guideline=c.configure_guideline, regulatory=c.regulatory,
                notes=c.notes, check_command=c.check_command, enabled=c.enabled,
                created_at=now, updated_at=now,
            )
            for c in sorted(src.controls, key=lambda c: c.position)
        ]
        await self._repo.save(copy)
        logger.info("Duplicated profile '%s' → '%s' (%d controls)",
                    src.name, name, len(copy.controls))
        return await self._repo.find_by_id(copy.id)

    # ── CSV export / template / import ────────────────────────────────────────
    # Column order for exports, templates and imports. `position` is optional on
    # import (row order is used when absent); `enabled` accepts true/false,
    # 1/0, yes/no, oui/non.
    CSV_COLUMNS = [
        "position", "kind", "section_id", "section", "title", "cis_id",
        "description", "recommended_value", "agreed_value", "risk_profile",
        "rationale", "validate_guideline", "configure_guideline", "regulatory",
        "notes", "check_command", "enabled",
    ]
    _CSV_REQUIRED = {"title"}
    _CSV_MAX_ROWS = 5000

    async def export_profile_csv(self, profile_id: str) -> tuple[str, str]:
        """Render a profile's controls as CSV. Returns (filename, csv_text)."""
        import csv as _csv
        import io
        import re as _re

        profile = await self._repo.find_by_id(profile_id)
        if not profile:
            raise ValidationError("Profile not found.")
        buf = io.StringIO()
        w = _csv.writer(buf, lineterminator="\r\n")
        w.writerow(self.CSV_COLUMNS)
        for c in sorted(profile.controls, key=lambda c: c.position):
            w.writerow([
                c.position, c.kind, c.section_id, c.section, c.title,
                c.cis_id or "", c.description or "", c.recommended_value or "",
                c.agreed_value or "", c.risk_profile or "", c.rationale or "",
                c.validate_guideline or "", c.configure_guideline or "",
                c.regulatory or "", c.notes or "", c.check_command or "",
                "true" if c.enabled else "false",
            ])
        slug = _re.sub(r"[^A-Za-z0-9._-]+", "-", profile.name).strip("-").lower() or "profile"
        return f"{slug}.csv", buf.getvalue()

    def csv_template(self) -> str:
        """A ready-to-edit CSV: header + one section row + two sample controls."""
        import csv as _csv
        import io

        buf = io.StringIO()
        w = _csv.writer(buf, lineterminator="\r\n")
        w.writerow(self.CSV_COLUMNS)
        w.writerow([1, "section", "5", "Access, Authentication & Authorization",
                    "5 — Access, Authentication & Authorization", "", "", "", "", "",
                    "", "", "", "", "", "", "true"])
        w.writerow([2, "control", "5.2.8", "Access, Authentication & Authorization",
                    "Ensure SSH root login is disabled", "5.2.8",
                    "Disallow direct root SSH logins.", "PermitRootLogin no",
                    "PermitRootLogin no", "High",
                    "Direct root logins remove accountability.",
                    "sshd -T | grep permitrootlogin",
                    "Set 'PermitRootLogin no' in /etc/ssh/sshd_config then restart sshd.",
                    "", "", "", "true"])
        w.writerow([3, "control", "5.2.9", "Access, Authentication & Authorization",
                    "Ensure SSH PermitEmptyPasswords is disabled", "5.2.9",
                    "Reject SSH logins with empty passwords.", "PermitEmptyPasswords no",
                    "", "High", "", "sshd -T | grep permitemptypasswords",
                    "Set 'PermitEmptyPasswords no' in /etc/ssh/sshd_config.",
                    "", "", "", "true"])
        return buf.getvalue()

    @staticmethod
    def _control_key(kind: str, section_id: str, title: str) -> tuple:
        """Identity used for duplicate detection and update matching: a control is
        'the same' when kind + normalised section_id (fallback title) match."""
        sid = (section_id or "").strip().lower()
        return (kind or "control", sid if sid else (title or "").strip().lower())

    @staticmethod
    def _parse_bool(value: str, row_num: int, errors: list[str]) -> bool:
        v = (value or "").strip().lower()
        if v in ("", "true", "1", "yes", "oui", "y", "x"):
            return True
        if v in ("false", "0", "no", "non", "n"):
            return False
        errors.append(f"row {row_num}: enabled must be true/false (got '{value}')")
        return True

    def _parse_csv_rows(self, text: str) -> tuple[list[dict], list[str]]:
        """Parse + validate CSV content. Returns (rows, errors); rows carry
        normalised values keyed by CSV_COLUMNS plus '_row' (line number)."""
        import csv as _csv
        import io

        errors: list[str] = []
        reader = _csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return [], ["The file is empty — download the template to get started."]
        headers = [h.strip() for h in reader.fieldnames]
        unknown = [h for h in headers if h and h not in self.CSV_COLUMNS]
        missing = self._CSV_REQUIRED - set(headers)
        if missing:
            errors.append(f"Missing required column(s): {', '.join(sorted(missing))}")
        if unknown:
            errors.append(
                f"Unknown column(s): {', '.join(unknown)} — expected columns are: "
                + ", ".join(self.CSV_COLUMNS)
            )
        if errors:
            return [], errors

        rows: list[dict] = []
        seen: dict[tuple, int] = {}
        for i, raw in enumerate(reader, start=2):  # header is line 1
            if i - 1 > self._CSV_MAX_ROWS:
                errors.append(f"Too many rows (max {self._CSV_MAX_ROWS}).")
                break
            vals = {k: (raw.get(k) or "").strip() for k in self.CSV_COLUMNS}
            if not any(vals.values()):
                continue  # skip blank lines
            kind = vals["kind"].lower() or "control"
            if kind not in ("control", "section"):
                errors.append(f"row {i}: kind must be 'control' or 'section' (got '{vals['kind']}')")
                continue
            if not vals["title"] and not vals["section_id"]:
                errors.append(f"row {i}: title (or section_id) is required")
                continue
            position: int | None = None
            if vals["position"]:
                try:
                    position = int(float(vals["position"]))
                except ValueError:
                    errors.append(f"row {i}: position must be a number (got '{vals['position']}')")
                    continue
            enabled = self._parse_bool(vals["enabled"], i, errors)

            # Duplicate detection WITHIN the file — the "repetitive controls" gate.
            key = self._control_key(kind, vals["section_id"], vals["title"])
            if key in seen:
                errors.append(
                    f"row {i}: duplicate of row {seen[key]} "
                    f"(same {kind} '{vals['section_id'] or vals['title']}') — "
                    "remove or merge repeated controls before importing"
                )
                continue
            seen[key] = i

            rows.append({
                **vals,
                "kind": kind,
                "title": vals["title"] or vals["section_id"],
                "position": position,
                "enabled": enabled,
                "_row": i,
            })
        if not rows and not errors:
            errors.append("The file contains no control rows.")
        return rows, errors

    async def import_profile_csv(
        self,
        text: str,
        profile_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        os_family: str | None = None,
        version: str | None = None,
    ) -> dict:
        """Apply a CSV to a profile — update an existing one or create a new one.

        Validation-first: the whole file is parsed and checked (unknown columns,
        missing titles, bad kinds/positions, duplicate controls within the file)
        and NOTHING is written unless the file is fully valid.

        Update mode (``profile_id`` given): rows are matched to existing controls
        by kind + section_id (fallback title). Matched rows update the control's
        fields — empty CSV cells leave the current value unchanged; changed
        fields are snapshotted to control history. Unmatched rows create new
        controls. Existing controls absent from the CSV are left untouched.

        Create mode (no ``profile_id``): a new custom profile named ``name`` is
        created with every row as a fresh control.
        """
        rows, errors = self._parse_csv_rows(text)
        if errors:
            raise ValidationError("CSV validation failed:\n" + "\n".join(errors[:25]))

        now = datetime.utcnow()

        if profile_id:
            profile = await self._repo.find_by_id(profile_id)
            if not profile:
                raise ValidationError("Profile not found.")
            self._ensure_editable(profile)
            existing = {
                self._control_key(c.kind, c.section_id, c.title): c
                for c in profile.controls
            }
            created = updated = unchanged = 0
            max_pos = max((c.position for c in profile.controls), default=0)
            for r in rows:
                key = self._control_key(r["kind"], r["section_id"], r["title"])
                current = existing.get(key)
                if current is None:
                    max_pos += 1
                    data = {k: (r[k] or None) for k in self.CSV_COLUMNS
                            if k not in ("position", "enabled")}
                    data["position"] = r["position"] if r["position"] is not None else max_pos
                    data["enabled"] = r["enabled"]
                    await self.add_control(profile_id, data)
                    created += 1
                else:
                    changes: dict = {}
                    for fld in self.CSV_COLUMNS:
                        if fld in ("position", "enabled"):
                            continue
                        val = r[fld]
                        if val and val != (getattr(current, fld) or ""):
                            changes[fld] = val
                    if r["position"] is not None and r["position"] != current.position:
                        changes["position"] = r["position"]
                    if r["enabled"] != current.enabled:
                        changes["enabled"] = r["enabled"]
                    if changes:
                        await self.update_control(current.id, changes)
                        updated += 1
                    else:
                        unchanged += 1
            profile.updated_at = now
            await self._repo.update(profile)
            fresh = await self._repo.find_by_id(profile_id)
            return {
                "mode": "update", "profile_id": profile_id, "profile_name": fresh.name,
                "created": created, "updated": updated, "unchanged": unchanged,
                "total_rows": len(rows), "control_count": fresh.control_count,
            }

        # Create mode
        pname = (name or "").strip()
        if not pname:
            raise ValidationError("A profile name is required to create a profile from CSV.")
        profile = await self.create_profile({
            "name": pname, "description": description,
            "os_family": os_family, "version": version,
        })
        for order, r in enumerate(rows, start=1):
            data = {k: (r[k] or None) for k in self.CSV_COLUMNS
                    if k not in ("position", "enabled")}
            data["position"] = r["position"] if r["position"] is not None else order
            data["enabled"] = r["enabled"]
            await self.add_control(profile.id, data)
        fresh = await self._repo.find_by_id(profile.id)
        return {
            "mode": "create", "profile_id": profile.id, "profile_name": fresh.name,
            "created": len(rows), "updated": 0, "unchanged": 0,
            "total_rows": len(rows), "control_count": fresh.control_count,
        }
