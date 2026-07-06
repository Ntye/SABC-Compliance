"""
Per-family artifact generation (Section 2).

From a referential profile, generate:

  * a Puppet module (``sabc_hardening``) — ONE class per control, each branching
    internally on ``$facts['os']['family']`` ('Debian' vs 'RedHat') so a single
    class name works across the whole family. The enforcement body is the
    family's **Configure** procedure, run idempotently: ``exec { configure,
    unless => validate }`` — the control's own Validate procedure is the guard,
    so an already-compliant node is a no-op.
  * an InSpec profile — ONE control per referential control, guarded by
    ``os.family`` so only the family-correct check runs on a given node. The
    check runs the family's **Validate** procedure and asserts exit status 0.

Rules (honest generation):
  * Only families listed in ``applies_to`` that ALSO have non-empty, runnable
    guidance are generated. A family whose guidance is empty (or is prose with
    no runnable commands) is reported as ``implementation pending:
    <control_id>/<family>`` and NEVER emitted as an un-authored fix.
  * Level is NOT a code concern — every control's class/InSpec control is
    emitted regardless of CIS Level. Which ones a node applies is decided by its
    TIER at scan/enforce time (the platform passes the applicable subset).
  * Branch on os.family, never on distro names.

The generator is pure/testable; a use case writes the tree at seed time.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field

from core.domain.entities import Profile, ProfileControl

# Facter family value per referential family token.
_FACTER_FAMILY = {"debian": "Debian", "redhat": "RedHat"}


def _puppet_key(control: ProfileControl) -> str:
    """Puppet class name segment: a valid class name from the control key/id."""
    base = control.control_key or (control.control_id or control.id)
    seg = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")
    if not seg or not seg[0].isalpha():
        seg = "c_" + seg
    return seg


# Public alias: enforcement resolves which sabc_hardening::<key> classes to
# apply for a node, and must derive the same keys this generator wrote.
def puppet_key(control: ProfileControl) -> str:
    return _puppet_key(control)


def extract_shell(guidance: str | None) -> str:
    """Extract a runnable shell body from a Validate/Configure cell.

    Pulls the FIRST fenced code block. A block that is a script (has a shebang
    or is multi-line) is kept verbatim; a block of prompt-style command lines
    (``# cmd`` / ``$ cmd``) has the leading root/user prompt stripped so the
    command actually runs (otherwise ``# apt …`` would be a no-op comment).

    Returns "" when there is no runnable command (prose-only or empty), which
    the caller treats as implementation-pending.
    """
    text = guidance or ""
    # Drop the SABC provenance banner lines before looking for code.
    text = "\n".join(l for l in text.splitlines() if not l.startswith("# [SABC]"))

    blocks = re.findall(r"```[a-zA-Z0-9_+-]*\n(.*?)```", text, re.S)
    if not blocks:
        return ""
    body = blocks[0].strip("\n")
    if not body.strip():
        return ""

    lines = body.splitlines()
    has_prompt = any(re.match(r"^\s*[#$]\s\S", ln) for ln in lines)
    is_script = body.lstrip().startswith("#!") or (
        not has_prompt
        and any(tok in body for tok in ("for ", "while ", "if ", "{", "done", "fi", "esac", "|"))
    )
    if is_script:
        # A full audit/remediation script — keep verbatim (it self-contains its
        # own logic and, for RHEL-safe CIS scripts, self-detects the pkg mgr).
        return body.rstrip()

    if has_prompt:
        # CIS convention: command lines carry a root/user prompt ('# '/'$ ') and
        # any other lines are EXPECTED OUTPUT. Keep only the prompted commands
        # (prompt stripped) so we never run the sample output as a command.
        cmds: list[str] = []
        for ln in lines:
            m = re.match(r"^\s*[#$]\s(?=\S)(.*)$", ln.rstrip())
            if m:
                cmds.append(m.group(1))
            elif cmds and cmds[-1].rstrip().endswith("\\"):
                cmds.append(ln.strip())  # continuation of a wrapped command
        return "\n".join(cmds).strip()

    # No prompt and not a script → a block of bare command(s). Keep every
    # non-empty line as a command.
    return "\n".join(l for l in (ln.rstrip() for ln in lines) if l.strip()).strip()


def _puppet_escape(cmd: str) -> str:
    """Escape a shell body for a single-quoted Puppet string."""
    return cmd.replace("\\", "\\\\").replace("'", "\\'")


@dataclass
class GenerationResult:
    generated: list[str] = field(default_factory=list)         # control_id/family
    pending: list[str] = field(default_factory=list)           # "control_id/family: reason"
    files_written: int = 0

    def merge(self, other: "GenerationResult") -> None:
        self.generated.extend(other.generated)
        self.pending.extend(other.pending)
        self.files_written += other.files_written


# ── Puppet module ─────────────────────────────────────────────────────────────

def _puppet_class(control: ProfileControl) -> tuple[str, list[str]]:
    """Render one Puppet class. Returns (manifest_text, pending[])."""
    key = _puppet_key(control)
    pending: list[str] = []
    branches: list[str] = []

    for fam in control.families():
        facter = _FACTER_FAMILY.get(fam)
        if not facter:
            continue
        configure = extract_shell(control.configure_for(fam))
        if not configure:
            pending.append(f"{control.control_id}/{fam}: no runnable Configure guidance")
            continue
        validate = extract_shell(control.validate_for(fam))
        guard = ""
        if validate:
            guard = f"    unless   => @(SABC_CHK/L),\n{_heredoc(validate, 'SABC_CHK')}    | SABC_CHK\n"
        branches.append(
            f"  if $facts['os']['family'] == '{facter}' {{\n"
            f"    exec {{ 'sabc_{key}_{fam}':\n"
            f"      command  => @(SABC_CMD/L),\n{_heredoc(configure, 'SABC_CMD')}      | SABC_CMD\n"
            f"      provider => 'shell',\n"
            f"      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],\n"
            f"{guard}"
            f"      logoutput => 'on_failure',\n"
            f"    }}\n"
            f"  }}"
        )

    title = (control.title or control.control_id or "").replace("\n", " ")
    lvl = control.cis_level
    header = (
        f"# {control.control_id} (CIS Level {lvl}) — {title}\n"
        f"# Generated from the SABC referential. Enforcement is the family's own\n"
        f"# Configure procedure, run only when the Validate procedure fails.\n"
        f"class sabc_hardening::{key} {{\n"
    )
    if not branches:
        body = "  # No runnable enforcement authored for any applicable family.\n"
    else:
        body = "\n".join(branches) + "\n"
    return header + body + "}\n", pending


def _heredoc(script: str, tag: str) -> str:
    indent = "        "
    lines = script.splitlines() or [""]
    return "".join(f"{indent}{ln}\n" for ln in lines)


def generate_puppet_module(profile: Profile, target_dir: str) -> GenerationResult:
    """Write the sabc_hardening Puppet module for every control of *profile*."""
    manifests = os.path.join(target_dir, "manifests")
    os.makedirs(manifests, exist_ok=True)
    # Clean previously generated per-control manifests (idempotent regeneration).
    for f in os.listdir(manifests):
        if f.endswith(".pp") and f != "init.pp":
            os.remove(os.path.join(manifests, f))

    result = GenerationResult()
    class_names: list[str] = []
    for c in profile.active_controls():
        text, pending = _puppet_class(c)
        key = _puppet_key(c)
        with open(os.path.join(manifests, f"{key}.pp"), "w", encoding="utf-8") as fh:
            fh.write(text)
        result.files_written += 1
        class_names.append(key)
        result.pending.extend(pending)
        for fam in c.families():
            if f"{c.control_id}/{fam}" not in " ".join(result.pending):
                result.generated.append(f"{c.control_id}/{fam}")

    # init.pp: takes the tier-applicable control keys and includes that subset.
    # Level gating is the tier's job — every class exists; inclusion is selected.
    init = (
        "# sabc_hardening — built-in hardening module generated from the SABC\n"
        "# referential. One class per control; each branches on os.family so the\n"
        "# same class works across Ubuntu/Debian/Mint and Alma/Rocky/RHEL/CentOS.\n"
        "#\n"
        "# @param controls  Control keys (tier-applicable subset) to enforce. When\n"
        "#   empty, ALL controls are enforced (Level 1 + Level 2, both families).\n"
        "class sabc_hardening (\n"
        "  Array[String] $controls = [],\n"
        ") {\n"
        "  $selected = empty($controls) ? {\n"
        f"    true    => {_puppet_array(class_names)},\n"
        "    default => $controls,\n"
        "  }\n"
        "  $selected.each |$c| {\n"
        "    include \"sabc_hardening::${c}\"\n"
        "  }\n"
        "}\n"
    )
    with open(os.path.join(manifests, "init.pp"), "w", encoding="utf-8") as fh:
        fh.write(init)
    result.files_written += 1

    # Minimal module metadata so `puppet apply`/agent can resolve it.
    with open(os.path.join(target_dir, "metadata.json"), "w", encoding="utf-8") as fh:
        fh.write(
            '{\n  "name": "sabc-sabc_hardening",\n'
            '  "version": "1.0.0",\n'
            '  "author": "SABC Compliance Platform (generated)",\n'
            '  "summary": "Generated hardening module from the SABC referential",\n'
            '  "license": "proprietary",\n'
            '  "dependencies": [],\n'
            '  "operatingsystem_support": [\n'
            '    {"operatingsystem": "Ubuntu"}, {"operatingsystem": "Debian"},\n'
            '    {"operatingsystem": "RedHat"}, {"operatingsystem": "Rocky"},\n'
            '    {"operatingsystem": "AlmaLinux"}, {"operatingsystem": "CentOS"}\n'
            '  ]\n}\n'
        )
    result.files_written += 1
    return result


def _puppet_array(items: list[str]) -> str:
    inner = ", ".join(f"'{i}'" for i in items)
    return f"[{inner}]"


# ── InSpec profile ────────────────────────────────────────────────────────────

def _inspec_control(control: ProfileControl) -> tuple[str, list[str]]:
    key = _puppet_key(control)
    pending: list[str] = []
    checks: list[str] = []
    for fam in control.families():
        validate = extract_shell(control.validate_for(fam))
        if not validate:
            pending.append(f"{control.control_id}/{fam}: no runnable Validate guidance")
            continue
        # Run the family's validate procedure; pass iff it exits 0. Guarded so
        # only the node's family runs its own check.
        checks.append(
            f"  if os[:family] == '{fam}'\n"
            f"    describe command(<<-'SABC_V'.chomp) do\n"
            f"{_ruby_heredoc(validate)}"
            f"    SABC_V\n"
            f"      its('exit_status') {{ should cmp 0 }}\n"
            f"    end\n"
            f"  end"
        )
    title = (control.title or control.control_id or "").replace("'", " ").replace("\n", " ")
    lvl = control.cis_level
    impact = "0.7" if lvl == 2 else "0.5"
    header = (
        f"control '{control.control_id}' do\n"
        f"  title '{title}'\n"
        f"  impact {impact}\n"
        f"  tag cis_level: {lvl}\n"
        f"  tag control_key: '{key}'\n"
    )
    if not checks:
        body = "  describe 'implementation pending' do\n    skip 'no runnable validation authored for this node family'\n  end\n"
    else:
        body = "\n".join(checks) + "\n"
    return header + body + "end\n", pending


def _ruby_heredoc(script: str) -> str:
    indent = "      "
    return "".join(f"{indent}{ln}\n" for ln in (script.splitlines() or [""]))


def generate_inspec_profile(profile: Profile, target_dir: str,
                            name: str = "sabc-baseline") -> GenerationResult:
    controls_dir = os.path.join(target_dir, "controls")
    if os.path.isdir(controls_dir):
        shutil.rmtree(controls_dir)
    os.makedirs(controls_dir, exist_ok=True)

    result = GenerationResult()
    for c in profile.active_controls():
        text, pending = _inspec_control(c)
        with open(os.path.join(controls_dir, f"{_puppet_key(c)}.rb"), "w", encoding="utf-8") as fh:
            fh.write(text)
        result.files_written += 1
        result.pending.extend(pending)
        for fam in c.families():
            if f"{c.control_id}/{fam}" not in " ".join(result.pending):
                result.generated.append(f"{c.control_id}/{fam}")

    with open(os.path.join(target_dir, "inspec.yml"), "w", encoding="utf-8") as fh:
        fh.write(
            f"name: {name}\n"
            f"title: SABC Baseline (generated, multi-OS)\n"
            f"maintainer: SABC Compliance Platform\n"
            f"license: proprietary\n"
            f"summary: Generated from the unified SABC referential; controls guarded by os.family.\n"
            f"version: {profile.version}\n"
            f"supports:\n"
            f"  - platform-family: debian\n"
            f"  - platform-family: redhat\n"
        )
    result.files_written += 1
    return result


# ── Seed-time generation use case ─────────────────────────────────────────────

class GenerateBuiltinArtifactsUseCase:
    """Regenerate the built-in sabc_hardening Puppet module and sabc-baseline
    InSpec profile from a profile (the SABC Baseline) at seed time.

    Idempotent: safe to call whenever the referential is (re)seeded. Returns a
    combined result including the implementation-pending list (controls/families
    with no runnable authored guidance)."""

    def __init__(self, profile_repo, puppet_module_dir: str, inspec_profile_dir: str) -> None:
        self._repo = profile_repo
        self._puppet_dir = puppet_module_dir
        self._inspec_dir = inspec_profile_dir

    async def execute(self, profile_id: str) -> GenerationResult:
        profile = await self._repo.find_by_id(profile_id)
        if not profile:
            raise ValueError(f"Profile '{profile_id}' not found")
        result = GenerationResult()
        result.merge(generate_puppet_module(profile, self._puppet_dir))
        result.merge(generate_inspec_profile(profile, self._inspec_dir))
        return result
