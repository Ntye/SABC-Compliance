"""Tests for the Red Hat guidance derivation used to build the SABC Baseline seed.

Red Hat guidance is authored from the CIS AlmaLinux 8 Benchmark (cis_alma8.ALMA8)
for controls that diverge from Debian, copied verbatim for family-neutral
controls, and marked Not-Applicable (exit 101) for Debian-only controls.
"""
from __future__ import annotations

import csv
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from redhat_translation import derive_redhat  # noqa: E402
from cis_alma8 import ALMA8  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(os.path.dirname(HERE), "sabc_baseline.csv")


class TestDeriveRedHat:
    def test_empty_source_yields_empty(self) -> None:
        text, prov = derive_redhat("JR2.C.9.9.9", "validate", "")
        assert text == "" and prov == "empty"

    def test_alma_authored_control_uses_benchmark_content(self) -> None:
        # CUPS -> CIS AlmaLinux "print server services are not in use": rpm/dnf.
        text, prov = derive_redhat("JR2.C.2.2.2", "validate", "# dpkg-query -W cups")
        assert prov == "alma"
        assert "CIS AlmaLinux 8" in text
        assert "rpm -q cups" in text
        assert "dpkg" not in text and "apt" not in text

    def test_alma_na_control_exits_101(self) -> None:
        # prelink has no CIS AlmaLinux 8 analogue -> Not Applicable on RHEL.
        text, prov = derive_redhat("JR2.C.1.4.1", "validate", "# dpkg-query -W prelink")
        assert prov == "alma-na"
        assert "exit 101" in text and "Not applicable" in text

    def test_family_neutral_field_copies_debian(self) -> None:
        # A sysctl/file check with no Debian-only tooling runs as-is on RHEL.
        deb = "```bash\ngrep -Eq '^\\s*UMASK\\s+027' /etc/login.defs || exit 1\n```"
        text, prov = derive_redhat("JR2.C.4.5.2", "validate", deb)
        assert prov == "neutral"
        assert "/etc/login.defs" in text and "exit 101" not in text

    def test_unmapped_debian_specific_field_is_not_applicable(self) -> None:
        # A control with apt/dpkg and no AlmaLinux mapping must NOT run apt on RHEL.
        text, prov = derive_redhat("JR2.C.9.9.9", "configure", "# apt install somepkg")
        assert prov == "na"
        assert "apt" not in text and "Not applicable" in text

    def test_no_redhat_body_ever_runs_apt_or_dpkg(self) -> None:
        for cid, entry in ALMA8.items():
            if entry.get("na"):
                continue
            for field in ("validate", "configure"):
                text, _ = derive_redhat(cid, field, "# dpkg-query -W x")
                assert not re.search(r"\b(apt|apt-get|dpkg|dpkg-query)\b", text), f"{cid}/{field}"


class TestGeneratedSeed:
    """Guards on the committed artifact so a bad regeneration is caught."""

    @pytest.fixture(scope="class")
    def rows(self) -> list[dict]:
        with open(CSV_PATH, encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def test_seed_exists_and_has_206_controls(self, rows: list[dict]) -> None:
        assert len([r for r in rows if r["Type"] == "control"]) == 206

    def test_every_redhat_control_has_both_columns_filled(self, rows: list[dict]) -> None:
        for r in rows:
            if r["Type"] != "control":
                continue
            if "redhat" not in (r["Applies To"] or "debian;redhat").lower():
                continue
            assert r["Validate — Red Hat family"].strip(), f"{r['Control ID']} RH validate empty"
            assert r["Configure — Red Hat family"].strip(), f"{r['Control ID']} RH configure empty"

    def test_section_rows_have_no_generated_guidance(self, rows: list[dict]) -> None:
        for r in rows:
            if r["Type"] == "section":
                assert not r["Validate — Red Hat family"].strip()
                assert not r["Configure — Red Hat family"].strip()

    def test_no_apt_or_dpkg_in_any_redhat_body(self, rows: list[dict]) -> None:
        for r in rows:
            if r["Type"] != "control":
                continue
            for col in ("Validate — Red Hat family", "Configure — Red Hat family"):
                body = "\n".join(l for l in r[col].splitlines() if not l.startswith("# [SABC]"))
                assert not re.search(r"\b(apt|apt-get|dpkg|dpkg-query)\b", body), \
                    f"{r['Control ID']}/{col} still references Debian package tooling"

    def test_control_key_is_slug_of_control_id(self, rows: list[dict]) -> None:
        sample = next(r for r in rows if r["Control ID"] == "JR2.C.1.1.1")
        assert sample["Control Key"] == "jr2_c_1_1_1"
