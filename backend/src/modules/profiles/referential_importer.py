"""
Unified multi-OS referential importer (Section 1).

One referential sheet = one PROFILE. The importer is **UPSERT, never
wipe-and-rebuild**, keyed on the internal **Control ID** (e.g. "JR2.C.1.1.1"):

    * match existing control by (profile_id, control_id)
    * exists   → update fields, snapshot the prior state to edit history
    * new      → insert
    * previously present but absent now → mark status='retired' (soft; kept so
      historical reports can still read the retired control's state)

Honest tagging rules:
    * Control ID is THE key. Never key on CIS.
    * Control Key is auto-derived (slug of Control ID); any provided value is
      ignored.
    * Framework Reference is provenance text only — stored, never parsed.
    * CIS Level: 1 or 2; blank => 1.
    * Type='section' rows are grouping metadata (kept for display, excluded from
      artifact generation).

The same code path seeds the built-in SABC Baseline at first boot (Section 0)
and services runtime imports from the Profiles UI — there is no special case.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from core.domain.entities import Profile, ProfileControl
from core.domain.interfaces import IProfileRepository

logger = logging.getLogger(__name__)


def slugify_control_id(control_id: str) -> str:
    """Auto-derive the Control Key from the Control ID (lower snake slug)."""
    return re.sub(r"[^a-z0-9]+", "_", (control_id or "").strip().lower()).strip("_")


# Header aliases — tolerate the em-dash/en-dash/simple-dash variants and case,
# so a sheet exported to CSV in any of those forms imports cleanly.
def _norm_header(h: str) -> str:
    h = (h or "").strip().lower()
    h = h.replace("—", "-").replace("–", "-")
    h = re.sub(r"\s+", " ", h)
    return h


_COLUMN_MAP = {
    "control id": "control_id",
    "control key": "control_key",          # ignored (auto-derived)
    "type": "type",
    "section": "section",
    "title": "title",
    "applies to": "applies_to",
    "cis level": "cis_level",
    "framework reference": "framework_reference",
    "agreed value": "agreed_value",
    "description": "description",
    "security rationale": "rationale",
    "validate - debian family": "validate_debian",
    "configure - debian family": "configure_debian",
    "validate - red hat family": "validate_redhat",
    "configure - red hat family": "configure_redhat",
}


@dataclass
class ReferentialRow:
    """One parsed referential row (section or control) in canonical form."""
    control_id: str
    kind: str                     # "control" | "section"
    section_id: str               # grouping section id (parent section's control_id)
    section: str                  # section heading text
    title: str
    applies_to: str = "debian;redhat"
    cis_level: int = 1
    framework_reference: str | None = None
    agreed_value: str | None = None
    description: str | None = None
    rationale: str | None = None
    validate_debian: str | None = None
    configure_debian: str | None = None
    validate_redhat: str | None = None
    configure_redhat: str | None = None
    row_num: int = 0


def _cell(v) -> str:
    return "" if v is None else str(v).strip()


def _level(v: str) -> int:
    m = re.search(r"[12]", v or "")
    return int(m.group(0)) if m else 1


def parse_referential_records(records: list[dict], errors: list[str] | None = None) -> list[ReferentialRow]:
    """Parse a list of dict rows (any header dialect) into ReferentialRows.

    ``section_id`` is tracked as the most-recent section row's Control ID so
    controls carry a meaningful grouping id for display.
    """
    errs = errors if errors is not None else []
    rows: list[ReferentialRow] = []
    current_section_id = ""
    seen_ids: dict[str, int] = {}

    for i, raw in enumerate(records, start=2):  # header is line 1
        mapped = {}
        for k, v in raw.items():
            key = _COLUMN_MAP.get(_norm_header(k))
            if key:
                mapped[key] = _cell(v)
        cid = mapped.get("control_id", "")
        kind = (mapped.get("type") or "control").lower()
        if kind not in ("control", "section"):
            errs.append(f"row {i}: Type must be 'control' or 'section' (got '{mapped.get('type')}')")
            continue
        title = mapped.get("title") or cid
        if not cid and not title:
            continue  # blank line
        if not cid:
            errs.append(f"row {i}: Control ID is required (it is the key)")
            continue
        # Uniqueness is enforced on CONTROL rows only — Control ID is the key for
        # enforceable controls. Section rows are grouping metadata and the source
        # occasionally reuses a section id across sibling sections; that is
        # harmless (grouping is by section name for display).
        if kind == "control":
            if cid in seen_ids:
                errs.append(f"row {i}: duplicate Control ID '{cid}' (first at row {seen_ids[cid]})")
                continue
            seen_ids[cid] = i
        else:
            current_section_id = cid

        rows.append(ReferentialRow(
            control_id=cid,
            kind=kind,
            section_id=(cid if kind == "section" else (current_section_id or cid)),
            section=mapped.get("section") or "General",
            title=title,
            applies_to=(mapped.get("applies_to") or "debian;redhat").lower(),
            cis_level=_level(mapped.get("cis_level", "")),
            framework_reference=mapped.get("framework_reference") or None,
            agreed_value=mapped.get("agreed_value") or None,
            description=mapped.get("description") or None,
            rationale=mapped.get("rationale") or None,
            validate_debian=mapped.get("validate_debian") or None,
            configure_debian=mapped.get("configure_debian") or None,
            validate_redhat=mapped.get("validate_redhat") or None,
            configure_redhat=mapped.get("configure_redhat") or None,
            row_num=i,
        ))
    return rows


def parse_referential_csv(text: str, errors: list[str] | None = None) -> list[ReferentialRow]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        (errors if errors is not None else []).append("The file is empty.")
        return []
    return parse_referential_records(list(reader), errors)


class ReferentialImportError(Exception):
    """Raised when the referential file is structurally invalid."""


class ReferentialImportUseCase:
    """UPSERT a unified referential into a profile (create the profile if new)."""

    def __init__(self, repo: IProfileRepository) -> None:
        self._repo = repo

    def _row_to_control_fields(self, r: ReferentialRow) -> dict:
        return {
            "section_id": r.section_id,
            "section": r.section,
            "title": r.title,
            "kind": r.kind,
            "control_id": r.control_id,
            "control_key": slugify_control_id(r.control_id),  # auto; ignore input
            "applies_to": r.applies_to,
            "cis_level": r.cis_level,
            "framework_reference": r.framework_reference,     # provenance only
            "status": "active",
            "validate_debian": r.validate_debian,
            "configure_debian": r.configure_debian,
            "validate_redhat": r.validate_redhat,
            "configure_redhat": r.configure_redhat,
            # Legacy display mirrors (Debian family is the primary display).
            "validate_guideline": r.validate_debian,
            "configure_guideline": r.configure_debian,
            "agreed_value": r.agreed_value,
            "recommended_value": r.agreed_value,
            "description": r.description,
            "rationale": r.rationale,
        }

    @staticmethod
    def _snapshot(c: ProfileControl) -> str:
        import json
        return json.dumps({
            "control_id": c.control_id, "section_id": c.section_id,
            "section": c.section, "title": c.title, "kind": c.kind,
            "applies_to": c.applies_to, "cis_level": c.cis_level,
            "framework_reference": c.framework_reference, "status": c.status,
            "validate_debian": c.validate_debian, "configure_debian": c.configure_debian,
            "validate_redhat": c.validate_redhat, "configure_redhat": c.configure_redhat,
            "agreed_value": c.agreed_value, "description": c.description,
            "rationale": c.rationale, "enabled": c.enabled, "position": c.position,
        })

    async def import_referential(
        self,
        rows: list[ReferentialRow],
        *,
        profile_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        version: str | None = None,
        source: str = "custom",
        is_system: bool = False,
    ) -> dict:
        """Apply *rows* to a profile via UPSERT keyed on control_id.

        Returns a summary: {profile_id, created, updated, retired, unchanged,
        version, control_count}.
        """
        now = datetime.utcnow()

        profile = await self._repo.find_by_id(profile_id) if profile_id else None
        if profile is None:
            pid = profile_id or str(uuid.uuid4())
            profile = Profile(
                id=pid,
                name=(name or "Imported referential").strip(),
                description=description,
                os_family="linux",
                version=version or "1.0.0",
                source=source,
                is_system=is_system,
                controls=[],
                created_at=now,
                updated_at=now,
            )
            await self._repo.save(profile)
        else:
            if name:
                profile.name = name
            if description is not None:
                profile.description = description

        # Match key: control_id is THE key for enforceable controls. Section rows
        # are grouping metadata and the source occasionally reuses a section id
        # across siblings, so sections match on a composite (id + title) to keep
        # the upsert stable without spuriously colliding.
        def match_key(kind: str, control_id: str, title: str) -> str:
            return control_id if kind == "control" else f"{control_id}::{title}"

        existing = {
            match_key(c.kind, c.control_id, c.title): c
            for c in profile.controls
            if c.control_id
        }

        created = updated = retired = unchanged = 0
        seen: set[str] = set()

        for pos, r in enumerate(rows, start=1):
            key = match_key(r.kind, r.control_id, r.title)
            seen.add(key)
            fields = self._row_to_control_fields(r)
            fields["position"] = pos
            current = existing.get(key)
            if current is None:
                control = ProfileControl(
                    id=str(uuid.uuid4()),
                    profile_id=profile.id,
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                    **fields,
                )
                await self._repo.save_control(control)
                created += 1
            else:
                changed = any(
                    getattr(current, k) != v
                    for k, v in fields.items()
                    if k not in ("position",)
                ) or current.position != pos or current.status == "retired"
                if changed:
                    await self._repo.save_control_history(current.id, self._snapshot(current))
                    for k, v in fields.items():
                        setattr(current, k, v)
                    current.position = pos
                    current.status = "active"
                    current.updated_at = now
                    await self._repo.update_control(current)
                    updated += 1
                else:
                    unchanged += 1

        # Retire controls that were present before but are absent now.
        for key, c in existing.items():
            if key not in seen and c.status != "retired":
                await self._repo.save_control_history(c.id, self._snapshot(c))
                c.status = "retired"
                c.updated_at = now
                await self._repo.update_control(c)
                retired += 1

        # Version increments per import (create keeps the initial version).
        if version:
            profile.version = version
        elif created or updated or retired:
            profile.version = _bump_version(profile.version)
        profile.updated_at = now
        await self._repo.update(profile)

        fresh = await self._repo.find_by_id(profile.id)
        summary = {
            "profile_id": profile.id,
            "profile_name": fresh.name,
            "version": fresh.version,
            "created": created,
            "updated": updated,
            "retired": retired,
            "unchanged": unchanged,
            "control_count": fresh.control_count,
        }
        logger.info(
            "Referential import '%s' v%s: +%d ~%d retired=%d =%d",
            fresh.name, fresh.version, created, updated, retired, unchanged,
        )
        return summary


def _bump_version(version: str | None) -> str:
    """Increment the patch component of a semver-ish version string."""
    v = (version or "1.0.0").strip()
    parts = v.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except (ValueError, IndexError):
        return "1.0.1"
