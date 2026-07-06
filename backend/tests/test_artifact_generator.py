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

    def test_bare_command_block_kept_and_apt_made_noninteractive(self) -> None:
        # apt mutations otherwise stop at "Do you want to continue? [Y/n]" and
        # abort when run from an exec with no tty.
        out = extract_shell("Fix:\n```\napt purge autofs\n```")
        assert out == "DEBIAN_FRONTEND=noninteractive apt-get -y purge autofs"

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

    def test_broken_redirect_artifact_repaired(self) -> None:
        # "2>&1; then" arrives as "2> then" in several referential cells — that
        # redirects stderr to a file named "then" and breaks the if-statement.
        g = "```\nif command -v dpkg-query > /dev/null 2> then\nl_pq=1\nfi\ndone_marker\n```"
        out = extract_shell(g)
        assert "2>&1; then" in out and "2> then" not in out

    def test_placeholder_template_is_pending_not_command(self) -> None:
        # fstab template lines / <placeholders> are guidance, not commands.
        assert extract_shell("```\n# <device> /tmp <fstype> defaults,nosuid 0 0\n```") == ""
        assert extract_shell("```\n# usermod -s $(which nologin) <user>\n```") == ""

    def test_config_content_is_pending_not_command(self) -> None:
        assert extract_shell("```\n# Defaults use_pty\n```") == ""
        assert extract_shell("```\nrestrict -4 default kod nomodify\nrestrict -6 default kod\n```") == ""
        assert extract_shell("```\ntmpfs /dev/shm tmpfs defaults,rw,nosuid 0 0\n```") == ""

    def test_interactive_command_is_pending(self) -> None:
        assert extract_shell("```\n# crontab -u root -e\n```") == ""
        assert extract_shell("```\n# grub-mkpasswd-pbkdf2\n```") == ""

    def test_multiline_quoted_prompt_command_kept_whole(self) -> None:
        # A prompted printf whose quoted argument spans lines must not be cut
        # at the first line ('printf "' alone is a syntax error).
        g = '```\n# printf "\nnet.ipv4.ip_forward = 0\n" >> /etc/sysctl.d/60-sabc.conf\n```'
        out = extract_shell(g)
        assert out.startswith('printf "')
        assert 'net.ipv4.ip_forward = 0' in out
        assert out.rstrip().endswith('60-sabc.conf')


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

    def test_scripts_shipped_as_module_files_run_with_bash(self, tmp_path) -> None:
        # The CIS bodies are bash-only; they must run as real bash script files
        # (never /bin/sh -c strings) with stdin closed so nothing can hang.
        generate_puppet_module(profile([control("JR2.C.1")]), str(tmp_path))
        pp = (tmp_path / "manifests" / "jr2_c_1.pp").read_text()
        assert "find_file('sabc_hardening/jr2_c_1_debian_cfg.sh')" in pp
        assert "/bin/bash" in pp and "</dev/null" in pp
        cfg = (tmp_path / "files" / "jr2_c_1_debian_cfg.sh").read_text()
        chk = (tmp_path / "files" / "jr2_c_1_debian_chk.sh").read_text()
        assert cfg.startswith("#!/usr/bin/env bash")
        assert "touch /x" in cfg and "test -f /x" in chk

    def test_debian_only_control_emits_only_debian_branch(self, tmp_path) -> None:
        generate_puppet_module(profile([control("JR2.C.2", applies="debian")]), str(tmp_path))
        pp = (tmp_path / "manifests" / "jr2_c_2.pp").read_text()
        assert "'Debian'" in pp and "'RedHat'" not in pp
        assert not (tmp_path / "files" / "jr2_c_2_redhat_cfg.sh").exists()

    def test_empty_family_guidance_reported_pending_not_generated(self, tmp_path) -> None:
        c = control("JR2.C.3", crh="")   # redhat configure prose-only/empty
        res = generate_puppet_module(profile([c]), str(tmp_path))
        assert any("JR2.C.3/redhat" in p for p in res.pending)
        pp = (tmp_path / "manifests" / "jr2_c_3.pp").read_text()
        assert "'Debian'" in pp                 # debian still generated
        assert "sabc_jr2_c_3_redhat" not in pp  # redhat NOT generated

    def test_stale_script_files_removed_on_regeneration(self, tmp_path) -> None:
        (tmp_path / "files").mkdir()
        (tmp_path / "files" / "old_retired_cfg.sh").write_text("echo old")
        generate_puppet_module(profile([control("JR2.C.1")]), str(tmp_path))
        assert not (tmp_path / "files" / "old_retired_cfg.sh").exists()

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

    def test_metadata_has_keys_puppet_requires(self, tmp_path) -> None:
        # When metadata.json exists, Puppet's module loader raises MissingMetadata
        # ("No source module metadata provided for sabc_hardening") unless
        # source/author/version are ALL present — which excludes the module and
        # makes `class sabc_hardening` unresolvable at apply time.
        import json
        generate_puppet_module(profile([control("JR2.C.1")]), str(tmp_path))
        meta = json.loads((tmp_path / "metadata.json").read_text())
        for key in ("source", "author", "version", "name"):
            assert meta.get(key), f"metadata.json missing required key: {key}"


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
