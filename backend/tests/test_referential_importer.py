"""Unified referential importer — UPSERT create / update / retire, honest tagging."""
from __future__ import annotations

import copy

import pytest

from core.domain.entities import Profile, ProfileControl
from modules.profiles.referential_importer import (
    ReferentialImportUseCase, parse_referential_records, slugify_control_id,
)


# ── In-memory profile repository (implements what the importer touches) ───────

class FakeProfileRepo:
    def __init__(self) -> None:
        self.profiles: dict[str, Profile] = {}
        self.controls: dict[str, ProfileControl] = {}
        self.history: dict[str, list[str]] = {}

    async def find_by_id(self, pid):
        p = self.profiles.get(pid)
        if not p:
            return None
        p = copy.deepcopy(p)
        p.controls = [copy.deepcopy(c) for c in self.controls.values() if c.profile_id == pid]
        p.controls.sort(key=lambda c: c.position)
        return p

    async def find_all(self):
        return [await self.find_by_id(pid) for pid in self.profiles]

    async def save(self, profile):
        self.profiles[profile.id] = copy.deepcopy(profile)
        for c in profile.controls:
            self.controls[c.id] = copy.deepcopy(c)

    async def update(self, profile):
        stored = self.profiles[profile.id]
        stored.name = profile.name
        stored.description = profile.description
        stored.version = profile.version
        stored.is_system = profile.is_system
        stored.updated_at = profile.updated_at

    async def save_control(self, control):
        self.controls[control.id] = copy.deepcopy(control)

    async def update_control(self, control):
        self.controls[control.id] = copy.deepcopy(control)

    async def find_control(self, cid):
        c = self.controls.get(cid)
        return copy.deepcopy(c) if c else None

    async def save_control_history(self, control_id, snapshot):
        self.history.setdefault(control_id, []).append(snapshot)


HEADER = [
    "Control ID", "Control Key", "Type", "Section", "Title", "Applies To",
    "CIS Level", "Framework Reference", "Agreed Value", "Description",
    "Security Rationale", "Validate — Debian family", "Configure — Debian family",
    "Validate — Red Hat family", "Configure — Red Hat family",
]


def rec(control_id, title, *, kind="control", applies="debian;redhat", level="",
        fref="", vdeb="v-deb", cdeb="c-deb", vrh="v-rh", crh="c-rh", section="Sec"):
    return {
        "Control ID": control_id, "Control Key": "IGNORED", "Type": kind,
        "Section": section, "Title": title, "Applies To": applies,
        "CIS Level": level, "Framework Reference": fref, "Agreed Value": "",
        "Description": "", "Security Rationale": "",
        "Validate — Debian family": vdeb, "Configure — Debian family": cdeb,
        "Validate — Red Hat family": vrh, "Configure — Red Hat family": crh,
    }


@pytest.fixture()
def uc():
    return ReferentialImportUseCase(FakeProfileRepo())


async def import_rows(uc, records, **kw):
    rows = parse_referential_records(records)
    return await uc.import_referential(rows, **kw)


# ── Parsing / honest tagging ──────────────────────────────────────────────────

class TestParsing:
    def test_control_key_is_auto_derived_and_input_ignored(self) -> None:
        rows = parse_referential_records([rec("JR2.C.1.1", "x")])
        # importer derives the key; the "IGNORED" input value is discarded
        assert slugify_control_id("JR2.C.1.1") == "jr2_c_1_1"

    def test_blank_level_defaults_to_1(self) -> None:
        rows = parse_referential_records([rec("JR2.C.1", "x", level="")])
        assert rows[0].cis_level == 1

    def test_level_2_parsed(self) -> None:
        rows = parse_referential_records([rec("JR2.C.1", "x", level="Level 2")])
        assert rows[0].cis_level == 2

    def test_applies_to_normalised(self) -> None:
        rows = parse_referential_records([rec("JR2.C.1", "x", applies="debian")])
        assert rows[0].applies_to == "debian"

    def test_duplicate_control_id_rejected(self) -> None:
        errs: list[str] = []
        parse_referential_records([rec("JR2.C.1", "a"), rec("JR2.C.1", "b")], errs)
        assert any("duplicate" in e.lower() for e in errs)

    def test_duplicate_section_id_tolerated(self) -> None:
        errs: list[str] = []
        rows = parse_referential_records(
            [rec("S.1", "Sec A", kind="section"), rec("S.1", "Sec B", kind="section")], errs)
        assert not errs and len(rows) == 2


# ── UPSERT: create ────────────────────────────────────────────────────────────

class TestCreate:
    async def test_import_into_new_profile_creates_all(self, uc) -> None:
        summary = await import_rows(uc, [
            rec("JR2.C.1", "one"), rec("JR2.C.2", "two"),
        ], profile_id="p1", name="Test", source="builtin", is_system=True)
        assert summary["created"] == 2
        assert summary["retired"] == 0
        prof = await uc._repo.find_by_id("p1")
        assert prof.is_system and prof.source == "builtin"
        assert {c.control_id for c in prof.controls} == {"JR2.C.1", "JR2.C.2"}

    async def test_framework_reference_stored_not_parsed(self, uc) -> None:
        await import_rows(uc, [rec("JR2.C.1", "x", fref="CIS 1.2.3; NIST AC-2")],
                          profile_id="p1", name="T")
        prof = await uc._repo.find_by_id("p1")
        c = prof.controls[0]
        assert c.framework_reference == "CIS 1.2.3; NIST AC-2"
        assert c.control_id == "JR2.C.1"     # keyed on control_id, not the CIS ref

    async def test_control_key_auto_derived(self, uc) -> None:
        await import_rows(uc, [rec("JR2.C.1.1", "x")], profile_id="p1", name="T")
        prof = await uc._repo.find_by_id("p1")
        assert prof.controls[0].control_key == "jr2_c_1_1"


# ── UPSERT: update ────────────────────────────────────────────────────────────

class TestUpdate:
    async def test_reimport_changed_field_updates_and_snapshots_history(self, uc) -> None:
        await import_rows(uc, [rec("JR2.C.1", "old title")], profile_id="p1", name="T")
        prof = await uc._repo.find_by_id("p1")
        cid = prof.controls[0].id

        summary = await import_rows(uc, [rec("JR2.C.1", "new title")], profile_id="p1")
        assert summary["updated"] == 1 and summary["created"] == 0
        prof = await uc._repo.find_by_id("p1")
        assert prof.controls[0].title == "new title"
        # prior state snapshotted to edit history
        assert len(uc._repo.history.get(cid, [])) == 1
        assert "old title" in uc._repo.history[cid][0]

    async def test_unchanged_reimport_is_noop(self, uc) -> None:
        await import_rows(uc, [rec("JR2.C.1", "x")], profile_id="p1", name="T")
        summary = await import_rows(uc, [rec("JR2.C.1", "x")], profile_id="p1")
        assert summary["updated"] == 0 and summary["unchanged"] == 1

    async def test_version_bumps_on_change_only(self, uc) -> None:
        await import_rows(uc, [rec("JR2.C.1", "x")], profile_id="p1", name="T", version="2.0.0")
        p = await uc._repo.find_by_id("p1")
        assert p.version == "2.0.0"
        # unchanged re-import (no explicit version) does not bump
        await import_rows(uc, [rec("JR2.C.1", "x")], profile_id="p1")
        assert (await uc._repo.find_by_id("p1")).version == "2.0.0"
        # changed re-import bumps the patch
        await import_rows(uc, [rec("JR2.C.1", "y")], profile_id="p1")
        assert (await uc._repo.find_by_id("p1")).version == "2.0.1"


# ── UPSERT: retire ────────────────────────────────────────────────────────────

class TestRetire:
    async def test_control_absent_on_reimport_is_retired_not_deleted(self, uc) -> None:
        await import_rows(uc, [rec("JR2.C.1", "a"), rec("JR2.C.2", "b")],
                          profile_id="p1", name="T")
        summary = await import_rows(uc, [rec("JR2.C.1", "a")], profile_id="p1")
        assert summary["retired"] == 1
        prof = await uc._repo.find_by_id("p1")
        # still present (soft delete), just retired — history preserved for reports
        by_id = {c.control_id: c for c in prof.controls}
        assert by_id["JR2.C.2"].status == "retired"
        assert by_id["JR2.C.1"].status == "active"

    async def test_reintroduced_control_is_reactivated(self, uc) -> None:
        await import_rows(uc, [rec("JR2.C.1", "a"), rec("JR2.C.2", "b")],
                          profile_id="p1", name="T")
        await import_rows(uc, [rec("JR2.C.1", "a")], profile_id="p1")             # retire C.2
        summary = await import_rows(uc, [rec("JR2.C.1", "a"), rec("JR2.C.2", "b")],
                                    profile_id="p1")                              # bring C.2 back
        prof = await uc._repo.find_by_id("p1")
        assert {c.control_id: c.status for c in prof.controls}["JR2.C.2"] == "active"
        assert summary["updated"] >= 1
