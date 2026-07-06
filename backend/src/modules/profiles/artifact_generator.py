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


# ── Guidance → runnable shell ─────────────────────────────────────────────────

# Copy/OCR artifact in several referential cells: "2>&1; then" arrives as
# "2> then", which redirects stderr to a file literally named "then" and breaks
# the surrounding if-statement. Never intentional — repair it.
_BROKEN_REDIRECT = re.compile(r"2>\s+then\b")

# Guidance placeholders that mark a block as a TEMPLATE, not a command:
# "<device>", "<userlist>", "<port>/<tcp or udp protocol>", "{NAME_OF_X}".
# "<" followed by a letter never occurs in real shell here (herestrings are
# "<<<", process substitution is "< <(", fd redirects are digits).
_PLACEHOLDER = re.compile(r"<[A-Za-z][^<>\n]*>|\{[A-Z][A-Z0-9_]{3,}\}")

# Commands that require a terminal/interactive input — running them from an
# exec can only hang or abort, so they are implementation-pending.
_INTERACTIVE = re.compile(
    r"^\s*(?:sudo\s+)?("
    r"crontab\b.*\s-e\b|visudo\b|sensible-editor\b|nano\b|vi\b|vim\b|"
    r"grub-mkpasswd-pbkdf2\b|passwd\s*$"
    r")"
)

# First tokens that identify CONFIG-FILE CONTENT the guidance shows for manual
# editing (sudoers, sshd_config, ntp/chrony, pwquality, PAM, postfix) — not
# executable commands.
_CONFIG_TOKENS = {
    "defaults", "restrict", "server", "pool", "inet_interfaces",
    "difok", "dictcheck", "maxrepeat", "minlen", "minclass", "enforcing",
    "auth", "account", "password", "session", "audit",
    "allowusers", "allowgroups", "denyusers", "denygroups",
    "banner", "protocol", "maxstartups",
}

# fstab-style template line: "<dev> /mount fstype defaults,opts 0 0".
_FSTAB_LINE = re.compile(r"^\S+\s+/\S*\s+\S+\s+\S*defaults\b")

_APT_CMD = re.compile(r"^(\s*)(?:sudo\s+)?apt(?:-get)?\s+(install|purge|remove|autoremove)\b(.*)$")


def _sanitize(body: str) -> str:
    return _BROKEN_REDIRECT.sub("2>&1; then", body)


def _noninteractive_apt(cmd: str) -> str:
    """Rewrite apt/apt-get mutations to be non-interactive (they otherwise stop
    at 'Do you want to continue? [Y/n]' and abort with no tty)."""
    lines = []
    for ln in cmd.splitlines():
        m = _APT_CMD.match(ln)
        if m:
            ln = (f"{m.group(1)}DEBIAN_FRONTEND=noninteractive "
                  f"apt-get -y {m.group(2)}{m.group(3)}")
        lines.append(ln)
    return "\n".join(lines)


# A /etc/security/limits.conf line: "<domain> <type> <item> <value>", where
# domain is *, a user, @group, or %group and type is hard/soft/-.
_LIMITS_LINE = re.compile(r"^(?:\*|-|@?[\w.-]+|%[\w.-]+)\s+(?:hard|soft|-)\s+\w+\s+\S+$")

# key=value config assignment for a settings file (chrony/timesyncd/sysconfig)
# where the key is an identifier — never a shell command invocation.
_CONFIG_ASSIGN = re.compile(r"^[A-Za-z_][\w-]*=\S")

# Lines that are prose/annotation, not commands (CIS mixes them into cells).
_PROSE_LINE = re.compile(r"^-?AND/OR-?$|^-AND-$|^-OR-$", re.I)


def _looks_like_config(cmds: str) -> bool:
    """True when extracted 'commands' are actually config-file content, prose,
    or an un-fillable template — running them as shell can only fail."""
    if _PLACEHOLDER.search(cmds):
        return True
    for ln in cmds.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("["):                      # ini/systemd section header
            return True
        if _FSTAB_LINE.match(ln) or _LIMITS_LINE.match(ln):
            return True
        if _CONFIG_ASSIGN.match(ln) or _PROSE_LINE.match(ln):
            return True
        first = ln.split()[0].rstrip(":").lower()
        if first in _CONFIG_TOKENS:
            return True
        if _INTERACTIVE.match(ln):
            return True
    return False


# Real shell control structure — word-bounded so "logfile" does NOT match "fi"
# and "restrict" does NOT match a keyword. Substring matching (the old approach)
# misclassified config lines like `Defaults logfile=...` as scripts, bypassing
# the config filter.
_SCRIPT_SIGNALS = re.compile(
    r"(?m)^\s*(?:for|while|until|if|case)\b"       # control opener at line start
    r"|^\s*[A-Za-z_]\w*\s*\(\)\s*\{?"              # function definition
    r"|\b(?:then|do|done|fi|esac)\b"              # block keyword (word-bounded)
    r"|\|\s*\S"                                    # pipe into another command
)


def _quote_balanced(text: str) -> bool:
    """Crude single/double-quote balance check (ignores escaping — good enough
    for deciding whether a prompted command continues on the next line)."""
    return text.count("'") % 2 == 0 and text.count('"') % 2 == 0


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
    body = _sanitize(blocks[0].strip("\n"))
    if not body.strip():
        return ""

    lines = body.splitlines()
    has_prompt = any(re.match(r"^\s*[#$]\s\S", ln) for ln in lines)
    is_script = body.lstrip().startswith("#!") or (
        not has_prompt and bool(_SCRIPT_SIGNALS.search(body))
    )
    if is_script:
        # A full audit/remediation script — keep verbatim (it self-contains its
        # own logic and, for RHEL-safe CIS scripts, self-detects the pkg mgr).
        return body.rstrip()

    if has_prompt:
        # CIS convention: command lines carry a root/user prompt ('# '/'$ ') and
        # any other lines are EXPECTED OUTPUT. Keep only the prompted commands
        # (prompt stripped). A command continues onto unprompted lines while it
        # ends with '\' OR its quotes are unbalanced (multi-line printf "...").
        cmds: list[str] = []
        for ln in lines:
            m = re.match(r"^\s*[#$]\s(?=\S)(.*)$", ln.rstrip())
            if m:
                cmds.append(m.group(1))
            elif cmds and (cmds[-1].rstrip().endswith("\\")
                           or not _quote_balanced("\n".join(cmds))):
                cmds.append(ln.rstrip())
        out = "\n".join(cmds).strip()
    else:
        # No prompt and not a script → a block of bare command(s). Keep every
        # non-empty line as a command.
        out = "\n".join(l for l in (ln.rstrip() for ln in lines) if l.strip()).strip()

    if not out or _looks_like_config(out):
        # Template/config content or interactive-only guidance — implementation
        # pending rather than shell noise (or worse) at enforce time.
        return ""
    return _noninteractive_apt(out)


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

# Every script runs under real bash (the CIS remediation scripts use bash-only
# syntax — herestrings, process substitution, [[ ]] — which Puppet's shell
# provider would otherwise hand to /bin/sh). globstar makes the CIS
# "/lib/modules/**/kernel/…" module-path globs expand as the scripts assume.
_SCRIPT_PRELUDE = (
    "#!/usr/bin/env bash\n"
    "# Generated by the SABC Compliance Platform — do not edit by hand.\n"
    "shopt -s globstar 2>/dev/null || true\n"
)


def _script_body(text: str) -> str:
    if text.lstrip().startswith("#!"):
        # Keep the script's own shebang line but still enable globstar.
        first, _, rest = text.partition("\n")
        return f"{first}\nshopt -s globstar 2>/dev/null || true\n{rest.rstrip()}\n"
    return _SCRIPT_PRELUDE + text.rstrip() + "\n"


def _puppet_class(control: ProfileControl) -> tuple[str, dict[str, str], list[str]]:
    """Render one Puppet class. Returns (manifest_text, script_files, pending[]).

    The Configure/Validate bodies are shipped as real files under the module's
    files/ directory and executed with bash — embedding them in the manifest as
    /bin/sh one-liners broke every bash-only CIS script. `</dev/null` guarantees
    nothing can sit waiting for terminal input.
    """
    key = _puppet_key(control)
    pending: list[str] = []
    branches: list[str] = []
    scripts: dict[str, str] = {}

    for fam in control.families():
        facter = _FACTER_FAMILY.get(fam)
        if not facter:
            continue
        configure = extract_shell(control.configure_for(fam))
        if not configure:
            pending.append(f"{control.control_id}/{fam}: no runnable Configure guidance")
            continue
        validate = extract_shell(control.validate_for(fam))

        cfg_name = f"{key}_{fam}_cfg.sh"
        scripts[cfg_name] = _script_body(configure)
        guard = ""
        if validate:
            chk_name = f"{key}_{fam}_chk.sh"
            scripts[chk_name] = _script_body(validate)
            guard = (
                f"    $chk_{fam} = find_file('sabc_hardening/{chk_name}')\n"
            )
        branches.append(
            f"  if $facts['os']['family'] == '{facter}' {{\n"
            f"    $cfg_{fam} = find_file('sabc_hardening/{cfg_name}')\n"
            f"{guard}"
            f"    exec {{ 'sabc_{key}_{fam}':\n"
            f"      command   => \"/bin/bash '${{cfg_{fam}}}' </dev/null\",\n"
            f"      provider  => 'shell',\n"
            f"      path      => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],\n"
            + (f"      unless    => \"/bin/bash '${{chk_{fam}}}' </dev/null\",\n" if validate else "")
            + f"      logoutput => 'on_failure',\n"
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
    return header + body + "}\n", scripts, pending


def generate_puppet_module(profile: Profile, target_dir: str) -> GenerationResult:
    """Write the sabc_hardening Puppet module for every control of *profile*."""
    manifests = os.path.join(target_dir, "manifests")
    files_dir = os.path.join(target_dir, "files")
    os.makedirs(manifests, exist_ok=True)
    os.makedirs(files_dir, exist_ok=True)
    # Clean previously generated artifacts (idempotent regeneration).
    for f in os.listdir(manifests):
        if f.endswith(".pp") and f != "init.pp":
            os.remove(os.path.join(manifests, f))
    for f in os.listdir(files_dir):
        if f.endswith(".sh"):
            os.remove(os.path.join(files_dir, f))

    result = GenerationResult()
    class_names: list[str] = []
    for c in profile.active_controls():
        text, scripts, pending = _puppet_class(c)
        key = _puppet_key(c)
        with open(os.path.join(manifests, f"{key}.pp"), "w", encoding="utf-8") as fh:
            fh.write(text)
        result.files_written += 1
        for name, content in scripts.items():
            with open(os.path.join(files_dir, name), "w", encoding="utf-8") as fh:
                fh.write(content)
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
    # When metadata.json EXISTS, Puppet's module loader validates it and raises
    # MissingMetadata ("No source module metadata provided for sabc_hardening")
    # if any of source/author/version is absent — which excludes the module and
    # makes `class sabc_hardening` unresolvable. So "source" is mandatory here.
    with open(os.path.join(target_dir, "metadata.json"), "w", encoding="utf-8") as fh:
        fh.write(
            '{\n  "name": "sabc-sabc_hardening",\n'
            '  "version": "1.0.0",\n'
            '  "author": "SABC Compliance Platform (generated)",\n'
            '  "source": "generated://sabc-compliance-platform/referential",\n'
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
