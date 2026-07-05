"""Per-family artifact generation — extraction, family branching, pending reporting."""
from __future__ import annotations

import os

import pytest

from core.domain.entities import Profile, ProfileControl
from modules.profiles.artifact_generator import (
    extract_shell, generate_inspec_profile, generate_puppet_module,
)


# ── Shell extraction (the correctness keystone) ───────────────────────────────

class TestExtractShell:
    def test_prompt_block_keeps_command_drops_expected_output(self) -> None:
        g = (
            "Verify it is installed.\n```\n"
            "# dpkg-query -W apparmor\n\n"
            "apparmor install ok installed\n```"
        )
        out = extract_shell(g)
        assert out == "dpkg-query -W apparmor"      # output line dropped

    def test_bare_command_block_kept(self) -> None:
        assert extract_shell("Fix:\n```\napt purge autofs\n```") == "apt purge autofs"

    def test_script_block_kept_verbatim(self) -> None:
        g = "```\n#!/usr/bin/env bash\nfor x in a b; do echo $x; done\n```"
        out = extract_shell(g)
        assert out.startswith("#!/usr/bin/env bash")
        assert "for x in a b" in out

    def test_prose_only_returns_empty(self) -> None:
        assert extract_shell("Use visudo to edit the sudoers file.") == ""

    def test_empty_returns_empty(self) -> None:
        assert extract_shell("") == "" and extract_shell(None) == ""

    def test_provenance_banner_stripped(self) -> None:
        g = "# [SABC] derived...\n```\ndnf install -y firewalld\n```"
        assert extract_shell(g) == "dnf install -y firewalld"


# ── Fixtures ──────────────────────────────────────────────────────────────────

def control(cid, *, applies="debian;redhat", level=1,
            vdeb="```\n# test -f /x\n```", cdeb="```\n# touch /x\n```",
            vrh="```\n# test -f /y\n```", crh="```\n# touch /y\n```") -> ProfileControl:
    return ProfileControl(
        id=cid, profile_id="p", section_id="s", section="Sec", title=f"Ctl {cid}",
        kind="control", control_id=cid, control_key=cid.lower().replace(".", "_"),
        applies_to=applies, cis_level=level,
        validate_debian=vdeb, configure_debian=cdeb,
        validate_redhat=vrh, configure_redhat=crh,
    )


def profile(controls) -> Profile:
    return Profile(id="p", name="P", source="builtin", is_system=True,
                   version="1.0.0", controls=controls)


# ── Puppet generation ─────────────────────────────────────────────────────────

class TestPuppet:
    def test_one_class_per_control_branching_on_family(self, tmp_path) -> None:
        generate_puppet_module(profile([control("JR2.C.1")]), str(tmp_path))
        pp = (tmp_path / "manifests" / "jr2_c_1.pp").read_text()
        assert "class sabc_hardening::jr2_c_1" in pp
        assert "$facts['os']['family'] == 'Debian'" in pp
        assert "$facts['os']['family'] == 'RedHat'" in pp
        # enforcement guarded by the control's own validate (idempotent)
        assert "unless" in pp

    def test_configure_run_unless_validate(self, tmp_path) -> None:
        generate_puppet_module(profile([control("JR2.C.1")]), str(tmp_path))
        pp = (tmp_path / "manifests" / "jr2_c_1.pp").read_text()
        assert "touch /x" in pp and "test -f /x" in pp   # debian configure + guard

    def test_debian_only_control_emits_only_debian_branch(self, tmp_path) -> None:
        generate_puppet_module(profile([control("JR2.C.2", applies="debian")]), str(tmp_path))
        pp = (tmp_path / "manifests" / "jr2_c_2.pp").read_text()
        assert "'Debian'" in pp and "'RedHat'" not in pp

    def test_empty_family_guidance_reported_pending_not_generated(self, tmp_path) -> None:
        c = control("JR2.C.3", crh="")   # redhat configure prose-only/empty
        res = generate_puppet_module(profile([c]), str(tmp_path))
        assert any("JR2.C.3/redhat" in p for p in res.pending)
        pp = (tmp_path / "manifests" / "jr2_c_3.pp").read_text()
        assert "'Debian'" in pp                 # debian still generated
        assert "sabc_jr2_c_3_redhat" not in pp  # redhat NOT generated

    def test_init_includes_all_control_keys_by_default(self, tmp_path) -> None:
        generate_puppet_module(profile([control("JR2.C.1"), control("JR2.C.2")]), str(tmp_path))
        init = (tmp_path / "manifests" / "init.pp").read_text()
        assert "class sabc_hardening" in init
        assert "'jr2_c_1'" in init and "'jr2_c_2'" in init
        assert "$controls" in init              # tier passes the applicable subset

    def test_level_not_a_code_concern_both_levels_emitted(self, tmp_path) -> None:
        generate_puppet_module(
            profile([control("L1", level=1), control("L2", level=2)]), str(tmp_path))
        assert (tmp_path / "manifests" / "l1.pp").exists()
        assert (tmp_path / "manifests" / "l2.pp").exists()


# ── InSpec generation ─────────────────────────────────────────────────────────

class TestInspec:
    def test_control_guarded_by_os_family(self, tmp_path) -> None:
        generate_inspec_profile(profile([control("JR2.C.1")]), str(tmp_path))
        rb = (tmp_path / "controls" / "jr2_c_1.rb").read_text()
        assert "control 'JR2.C.1'" in rb
        assert "os[:family] == 'debian'" in rb
        assert "os[:family] == 'redhat'" in rb
        assert "exit_status" in rb

    def test_redhat_only_control_guards_only_redhat(self, tmp_path) -> None:
        generate_inspec_profile(profile([control("R", applies="redhat")]), str(tmp_path))
        rb = (tmp_path / "controls" / "r.rb").read_text()
        assert "os[:family] == 'redhat'" in rb
        assert "os[:family] == 'debian'" not in rb

    def test_empty_validate_reported_pending(self, tmp_path) -> None:
        res = generate_inspec_profile(
            profile([control("JR2.C.9", vrh="")]), str(tmp_path))
        assert any("JR2.C.9/redhat" in p for p in res.pending)

    def test_inspec_yml_supports_both_families(self, tmp_path) -> None:
        generate_inspec_profile(profile([control("JR2.C.1")]), str(tmp_path))
        yml = (tmp_path / "inspec.yml").read_text()
        assert "platform-family: debian" in yml
        assert "platform-family: redhat" in yml
