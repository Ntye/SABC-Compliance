"""Tests for the Red Hat guidance derivation used to build the SABC Baseline seed."""
from __future__ import annotations

import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from redhat_translation import (  # noqa: E402
    OVERRIDES, derive_redhat, is_self_detecting, needs_override, translate_mechanical,
)

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(os.path.dirname(HERE), "sabc_baseline.csv")


class TestMechanical:
    def test_dpkg_query_becomes_rpm_q(self) -> None:
        src = "# dpkg-query -W -f='${binary:Package}\\t${Status}\\n' apparmor"
        out = translate_mechanical(src)
        assert "rpm -q apparmor" in out
        assert "dpkg-query" not in out

    def test_apt_purge_becomes_dnf_remove(self) -> None:
        assert "dnf remove -y autofs" in translate_mechanical("# apt purge autofs")

    def test_apt_install_becomes_dnf_install(self) -> None:
        assert "dnf install -y auditd" in translate_mechanical("# apt install auditd")

    def test_apt_get_variants(self) -> None:
        assert "dnf remove -y x" in translate_mechanical("apt-get remove x")
        assert "dnf makecache" in translate_mechanical("apt-get update")

    def test_family_agnostic_commands_untouched(self) -> None:
        for cmd in [
            "sysctl -w net.ipv4.ip_forward=0",
            "systemctl --now disable autofs",
            "modprobe -n -v cramfs",
            "chmod 0600 /etc/ssh/sshd_config",
            "stat -Lc '%a' /etc/passwd",
        ]:
            assert translate_mechanical(cmd) == cmd


class TestSelfDetecting:
    def test_script_that_branches_on_pkg_manager_is_left_verbatim(self) -> None:
        src = (
            'if command -v dpkg-query > /dev/null 2>&1; then\n'
            '  l_pq="dpkg-query -W"\n'
            'elif command -v rpm > /dev/null 2>&1; then\n'
            '  l_pq="rpm -q"\n'
            'fi'
        )
        assert is_self_detecting(src)
        text, prov = derive_redhat("JR2.C.1.7.1", "validate", src)
        assert prov == "cross"
        # The rpm branch is preserved exactly — detection logic intact.
        assert 'l_pq="rpm -q"' in text
        assert 'l_pq="dpkg-query -W"' in text


class TestOverrides:
    def test_ufw_control_is_authored_as_firewalld(self) -> None:
        text, prov = derive_redhat("JR2.C.3.4.1.1", "configure", "# apt install ufw")
        assert prov == "authored"
        assert "firewalld" in text
        # No ufw *command* is emitted (the word may appear as explanation only).
        import re
        assert not re.search(r"\bufw\s+(install|enable|allow|deny|status)", text)
        assert "dnf install -y firewalld" in text

    def test_apparmor_control_is_authored_as_selinux(self) -> None:
        text, prov = derive_redhat("JR2.C.1.5.1", "validate", "# dpkg-query -W apparmor")
        assert prov == "authored"
        assert "selinux" in text.lower()

    def test_needs_override_flags_divergent_tools(self) -> None:
        assert needs_override("ufw enable")
        assert needs_override("apparmor_status")
        assert needs_override("update-grub")
        assert needs_override("/etc/pam.d/common-password")
        assert not needs_override("sysctl -w x=0")


class TestEmpty:
    def test_empty_source_yields_empty(self) -> None:
        text, prov = derive_redhat("JR2.C.9.9.9", "validate", "")
        assert text == "" and prov == "empty"


class TestGeneratedSeed:
    """Guards on the committed artifact so a bad regeneration is caught."""

    @pytest.fixture(scope="class")
    def rows(self) -> list[dict]:
        with open(CSV_PATH, encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def test_seed_exists_and_has_206_controls(self, rows: list[dict]) -> None:
        controls = [r for r in rows if r["Type"] == "control"]
        assert len(controls) == 206

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

    def test_no_standalone_apt_verbs_in_redhat_bodies(self, rows: list[dict]) -> None:
        import re
        for r in rows:
            for col in ("Validate — Red Hat family", "Configure — Red Hat family"):
                body = "\n".join(l for l in r[col].splitlines() if not l.startswith("# [SABC]"))
                if "command -v rpm" in body or "rpm -q" in body:
                    continue  # self-detecting script — legitimately keeps dpkg branch
                assert not re.search(
                    r"^\s*#?\s*(apt(-get)?\s+(install|purge|remove|update|upgrade)|dpkg-query\s+-W\s+-f)",
                    body, re.M,
                ), f"{r['Control ID']}/{col} still has an untranslated package verb"

    def test_control_key_is_slug_of_control_id(self, rows: list[dict]) -> None:
        sample = next(r for r in rows if r["Control ID"] == "JR2.C.1.1.1")
        assert sample["Control Key"] == "jr2_c_1_1_1"
