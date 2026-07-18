"""
Red Hat family guidance derivation for the SABC Baseline referential.

The source spreadsheet ships complete Debian-family Validate/Configure guidance
but leaves the Red Hat-family columns empty. This module derives the Red Hat
guidance so the built-in referential is complete for BOTH families on day one.

Two mechanisms, applied in order:

1. **Authored overrides** (``OVERRIDES``) — for controls where the two families
   genuinely diverge (ufw↔firewalld, AppArmor↔SELinux, GRUB paths, PAM stack
   layout). These are hand-written to correct RHEL conventions.

2. **Mechanical translation** (``translate_mechanical``) — for the large
   majority whose only difference is the package manager. sysctl, modprobe,
   systemctl, and file-permission commands are identical across families, so
   only ``apt``/``dpkg`` verbs are rewritten to ``dnf``/``rpm``. These rules are
   deliberately conservative 1:1 substitutions.

Every derived cell is prefixed with a provenance marker so a reviewer can see
at a glance whether a cell was authored or mechanically derived. This module is
pure and unit-tested (``tests/test_redhat_translation.py``); the committed
``sabc_baseline.csv`` is regenerated from it by ``generate_seed.py``.

IMPORTANT: mechanically-derived Red Hat guidance is a best-effort 1:1 port and
should be reviewed by a RHEL subject-matter expert before being relied on for
production enforcement. The authored overrides encode standard RHEL practice.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cis_alma8 import ALMA8  # noqa: E402  (control_id -> RH guidance from CIS AlmaLinux 8)

PROV_AUTHORED = "# [SABC] Red Hat family guidance — authored for RHEL/Alma/Rocky.\n"
PROV_DERIVED = "# [SABC] Red Hat family guidance — derived from the Debian guidance (package manager mapped apt/dpkg to dnf/rpm; sysctl/systemctl/file checks are family-agnostic).\n"
PROV_CROSS = "# [SABC] Red Hat family guidance — the source procedure self-detects the package manager (it already branches on dpkg vs rpm) and runs correctly on the Red Hat family as-is.\n"
PROV_ALMA = "# [SABC] Red Hat family guidance — authored from the CIS AlmaLinux 8 Benchmark.\n"
PROV_NEUTRAL = "# [SABC] Red Hat family guidance — family-neutral procedure; the Debian commands (sysctl/systemctl/file/pam checks) run identically on the Red Hat family.\n"
PROV_NA = "# [SABC] Not applicable on the Red Hat family — no CIS AlmaLinux 8 equivalent for this Debian-specific control.\n"

# Exit code the scan/enforce pipeline treats as "control not applicable on this
# node" (kept in sync with artifact_generator.NA_EXIT_CODE).
_NA_EXIT = 101
_NA_VALIDATE = PROV_NA + f"```\n#!/usr/bin/env bash\nexit {_NA_EXIT}\n```"
_NA_CONFIGURE = PROV_NA  # no runnable body → nothing to enforce on RHEL

# Debian-only tooling: a field that mentions any of these cannot run on RHEL and,
# absent an explicit CIS-AlmaLinux mapping, is marked not-applicable rather than
# executed. sysctl/systemctl/chmod/grep on /etc are family-neutral and copy over.
_DEB_ONLY = re.compile(
    r"\b(apt|apt-get|dpkg|dpkg-query|dpkg-reconfigure|add-apt-repository|apt-mark|"
    r"apparmor|aa-status|aa-enforce|ufw|apport)\b|/etc/apt", re.I
)

def _fenced(shell: str) -> str:
    shell = (shell or "").strip()
    return f"```\n{shell}\n```" if shell else ""


# ── Mechanical package-manager translation ────────────────────────────────────
# Ordered (specific → general). Only package-manager verbs are rewritten; every
# other command (sysctl, systemctl, modprobe, stat, chmod, chown, awk, grep …)
# is identical across families and left untouched.
_RULES: list[tuple[re.Pattern[str], str]] = [
    # dpkg-query with a format string → rpm -q (drops the Debian-only format).
    # `[^']*` (no DOTALL) keeps the match on a single line so multi-line scripts
    # are not swallowed whole.
    (re.compile(r"dpkg-query\s+-W\s+-f=(['\"])[^'\"]*\1\s+"), "rpm -q "),
    (re.compile(r"dpkg-query\s+-W\b\s*"), "rpm -q "),
    (re.compile(r"dpkg\s+-s\s+"), "rpm -q "),
    (re.compile(r"dpkg\s+-l\s+"), "rpm -q "),
    (re.compile(r"dpkg\s+--verify\b"), "rpm -V"),
    # apt/apt-get verbs → dnf.
    (re.compile(r"apt(?:-get)?\s+purge\s+"), "dnf remove -y "),
    (re.compile(r"apt(?:-get)?\s+remove\s+--purge\s+"), "dnf remove -y "),
    (re.compile(r"apt(?:-get)?\s+remove\s+"), "dnf remove -y "),
    (re.compile(r"apt(?:-get)?\s+autoremove\b"), "dnf autoremove -y"),
    (re.compile(r"apt(?:-get)?\s+install\s+(?:-y\s+)?"), "dnf install -y "),
    (re.compile(r"apt(?:-get)?\s+update\b"), "dnf makecache"),
    (re.compile(r"apt(?:-get)?\s+upgrade\b"), "dnf upgrade -y"),
    (re.compile(r"\bapt-cache\s+policy\s+"), "dnf info "),
]

# Markers that indicate a control needs an authored override, not a mechanical
# port — a mechanical translation of these would be wrong or misleading.
_NEEDS_OVERRIDE = re.compile(r"\bufw\b|apparmor|update-grub|/boot/grub/grub\.cfg|common-(auth|password|account|session)", re.I)

# A source procedure is "self-detecting" when it already branches on which
# package manager is installed (checks for both dpkg and rpm). Those scripts run
# correctly on the Red Hat family verbatim, so they must not be piecemeal
# rewritten — that would corrupt the detection logic.
_SELF_DETECT = re.compile(r"command\s+-v\s+rpm|\brpm\s+-q", re.I)


def needs_override(debian_text: str) -> bool:
    """True when the Debian guidance references a family-divergent tool and so
    must be handled by an authored override rather than mechanical translation."""
    return bool(_NEEDS_OVERRIDE.search(debian_text or ""))


def is_self_detecting(debian_text: str) -> bool:
    """True when the procedure already handles the rpm/dpkg split itself."""
    t = debian_text or ""
    return bool(_SELF_DETECT.search(t)) and "dpkg" in t


def translate_mechanical(debian_text: str) -> str:
    """Rewrite package-manager verbs in *debian_text* for the Red Hat family.

    Everything that is family-agnostic (sysctl, systemctl, modprobe, file
    permissions, generic shell) is preserved verbatim. Returns the text
    unchanged when there is nothing to translate.
    """
    text = debian_text or ""
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    # Debian ships a couple of package aliases that differ on RHEL.
    text = text.replace("apparmor-utils", "")  # RHEL uses SELinux; handled by overrides
    return text


# ── Authored overrides for family-divergent controls ──────────────────────────
# Keyed by control_id → {"validate": ..., "configure": ...}. Authored to
# standard RHEL 8/9 practice (firewalld, SELinux, grub2, pam_pwquality/faillock).
# Only fields present here override the mechanical derivation.

OVERRIDES: dict[str, dict[str, str]] = {
    # ── 1.3.x GRUB (grub2 paths differ from Debian's grub) ───────────────────
    "JR2.C.1.3.1": {
        "validate": (
            "Verify the bootloader superuser and password are configured.\n"
            "```\n"
            "# grep -P '^\\h*set\\h+superusers' /boot/grub2/grub.cfg /boot/grub2/user.cfg 2>/dev/null\n"
            "# grep -P '^\\h*password' /boot/grub2/grub.cfg /boot/grub2/user.cfg 2>/dev/null\n"
            "```\n"
            "A `set superusers` line and a matching `password_pbkdf2` entry must be present."
        ),
        "configure": (
            "Set a GRUB2 boot password (RHEL/Alma/Rocky use grub2, not grub):\n"
            "```\n"
            "# grub2-setpassword\n"
            "# grub2-mkconfig -o /boot/grub2/grub.cfg   # BIOS\n"
            "# grub2-mkconfig -o /boot/efi/EFI/redhat/grub.cfg   # UEFI\n"
            "```"
        ),
    },
    "JR2.C.1.3.2": {
        "validate": (
            "Ensure permissions on the bootloader config are configured.\n"
            "```\n"
            "# stat -Lc 'Access: (%#a/%A) Uid: (%u/%U) Gid: (%g/%G)' /boot/grub2/grub.cfg\n"
            "```\n"
            "Expected: Uid 0/root, Gid 0/root, and mode 0600 or more restrictive."
        ),
        "configure": (
            "Restrict the grub2 config file:\n"
            "```\n"
            "# chown root:root /boot/grub2/grub.cfg\n"
            "# chmod 0600 /boot/grub2/grub.cfg\n"
            "```"
        ),
    },
    # ── 1.5.x Mandatory Access Control: AppArmor → SELinux ───────────────────
    "JR2.C.1.5.1": {
        "validate": (
            "Verify SELinux (the RHEL-family MAC system) is installed.\n"
            "```\n"
            "# rpm -q libselinux selinux-policy-targeted\n"
            "```\n"
            "Both packages must report as installed."
        ),
        "configure": (
            "Install SELinux (the RHEL-family equivalent of AppArmor):\n"
            "```\n"
            "# dnf install -y libselinux selinux-policy-targeted policycoreutils\n"
            "```"
        ),
    },
    "JR2.C.1.5.2": {
        "validate": (
            "Verify SELinux is not disabled in the bootloader and a policy is loaded.\n"
            "```\n"
            "# grep -P '^\\h*(GRUB_CMDLINE_LINUX(_DEFAULT)?=.*)(selinux=0|enforcing=0)' /etc/default/grub\n"
            "# grep -P '^\\h*SELINUX=' /etc/selinux/config\n"
            "```\n"
            "The first command must return nothing; SELINUX must be `enforcing` (or at minimum `permitting`)."
        ),
        "configure": (
            "Ensure SELinux is enabled at boot and enforcing:\n"
            "```\n"
            "# sed -ri 's/(selinux|enforcing)=0\\s*//g' /etc/default/grub\n"
            "# grub2-mkconfig -o /boot/grub2/grub.cfg\n"
            "# sed -ri 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config\n"
            "# setenforce 1\n"
            "```"
        ),
    },
    "JR2.C.1.5.3": {
        "validate": (
            "Verify the SELinux mode is Enforcing.\n"
            "```\n"
            "# getenforce\n"
            "Enforcing\n"
            "# grep -Pi '^\\h*SELINUX=enforcing' /etc/selinux/config\n"
            "```"
        ),
        "configure": (
            "Set SELinux to enforcing, now and persistently:\n"
            "```\n"
            "# setenforce 1\n"
            "# sed -ri 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config\n"
            "```"
        ),
    },
    "JR2.C.6.1.11": {
        "validate": (
            "Ensure SELinux denials are being logged/audited.\n"
            "```\n"
            "# systemctl is-enabled auditd\n"
            "# ausearch -m AVC -ts today 2>/dev/null | head\n"
            "```\n"
            "auditd must be enabled; AVC records are written there rather than to an AppArmor log."
        ),
        "configure": (
            "Ensure auditd is running so SELinux (AVC) denials are recorded:\n"
            "```\n"
            "# dnf install -y audit\n"
            "# systemctl --now enable auditd\n"
            "```"
        ),
    },
    # ── 3.4.x Host firewall: ufw → firewalld ─────────────────────────────────
    "JR2.C.3.4.1.1": {
        "validate": (
            "Verify a single host firewall is installed. RHEL-family uses firewalld:\n"
            "```\n"
            "# rpm -q firewalld\n"
            "```\n"
            "firewalld must be installed (and nftables present as its backend)."
        ),
        "configure": (
            "Install firewalld (the RHEL-family host firewall; ufw is Debian-only):\n"
            "```\n"
            "# dnf install -y firewalld\n"
            "```"
        ),
    },
    "JR2.C.3.4.1.3": {
        "validate": (
            "Ensure firewalld is enabled and running.\n"
            "```\n"
            "# systemctl is-enabled firewalld\n"
            "# systemctl is-active firewalld\n"
            "```\n"
            "Both must report enabled/active."
        ),
        "configure": (
            "Enable and start firewalld:\n"
            "```\n"
            "# systemctl --now enable firewalld\n"
            "```"
        ),
    },
    "JR2.C.3.4.1.4": {
        "validate": (
            "Ensure the loopback interface is trusted and loopback traffic from other zones is dropped.\n"
            "```\n"
            "# firewall-cmd --get-zone-of-interface=lo\n"
            "# firewall-cmd --list-all --zone=trusted\n"
            "```\n"
            "The `lo` interface must be bound to the `trusted` zone."
        ),
        "configure": (
            "Bind loopback to the trusted zone:\n"
            "```\n"
            "# firewall-cmd --permanent --zone=trusted --add-interface=lo\n"
            "# firewall-cmd --reload\n"
            "```"
        ),
    },
    "JR2.C.3.4.1.5": {
        "validate": (
            "Ensure firewalld drops unnecessary services and ports (default zone is restrictive).\n"
            "```\n"
            "# firewall-cmd --get-default-zone\n"
            "# firewall-cmd --list-all\n"
            "```\n"
            "Only explicitly required services/ports should be listed."
        ),
        "configure": (
            "Remove any service/port that is not required, e.g.:\n"
            "```\n"
            "# firewall-cmd --permanent --remove-service=<service>\n"
            "# firewall-cmd --permanent --remove-port=<port>/<proto>\n"
            "# firewall-cmd --reload\n"
            "```"
        ),
    },
    "JR2.C.3.4.1.6": {
        "validate": (
            "Ensure the firewalld default zone drops or rejects unmatched traffic.\n"
            "```\n"
            "# firewall-cmd --get-default-zone\n"
            "# firewall-cmd --permanent --zone=$(firewall-cmd --get-default-zone) --get-target\n"
            "```\n"
            "Target should be `DROP` (or `%%REJECT%%`) for a default-deny posture."
        ),
        "configure": (
            "Set the default zone target to DROP:\n"
            "```\n"
            "# firewall-cmd --permanent --zone=$(firewall-cmd --get-default-zone) --set-target=DROP\n"
            "# firewall-cmd --reload\n"
            "```"
        ),
    },
    "JR2.C.3.4.2.2": {
        "validate": (
            "Ensure nftables (the firewalld backend on RHEL) is the active backend.\n"
            "```\n"
            "# grep -P '^\\h*FirewallBackend=nftables' /etc/firewalld/firewalld.conf\n"
            "```"
        ),
        "configure": (
            "Ensure firewalld uses the nftables backend (default on RHEL 8+):\n"
            "```\n"
            "# sed -ri 's/^FirewallBackend=.*/FirewallBackend=nftables/' /etc/firewalld/firewalld.conf\n"
            "# systemctl restart firewalld\n"
            "```"
        ),
    },
    "JR2.C.3.4.3.1.3": {
        "validate": (
            "Ensure the host firewall is firewalld and iptables/nftables are not managed directly.\n"
            "```\n"
            "# systemctl is-active firewalld\n"
            "# systemctl is-enabled nftables 2>/dev/null || echo 'nftables service masked/inactive (managed by firewalld)'\n"
            "```"
        ),
        "configure": (
            "Let firewalld own the firewall; do not run a separate nftables service:\n"
            "```\n"
            "# systemctl --now enable firewalld\n"
            "# systemctl --now mask nftables 2>/dev/null || true\n"
            "```"
        ),
    },
    # ── 4.4.x / 4.5.2 PAM: Debian common-* → RHEL system-auth/password-auth ──
    "JR2.C.4.4.1": {
        "validate": (
            "Ensure the pam_pwquality module is present in the RHEL PAM stacks.\n"
            "```\n"
            "# grep -P 'pam_pwquality\\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth\n"
            "# rpm -q libpwquality\n"
            "```"
        ),
        "configure": (
            "Enable password quality via authselect (RHEL uses system-auth/password-auth, not common-password):\n"
            "```\n"
            "# dnf install -y libpwquality\n"
            "# authselect enable-feature with-pwquality\n"
            "# authselect apply-changes\n"
            "```"
        ),
    },
    "JR2.C.4.4.2": {
        "validate": (
            "Ensure password quality requirements are configured.\n"
            "```\n"
            "# grep -P '^\\h*(minlen|minclass|dcredit|ucredit|ocredit|lcredit)' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null\n"
            "```"
        ),
        "configure": (
            "Set the requirements in /etc/security/pwquality.conf (same file on both families):\n"
            "```\n"
            "# printf 'minlen = 14\\nminclass = 4\\n' >> /etc/security/pwquality.conf\n"
            "```"
        ),
    },
    "JR2.C.4.4.3": {
        "validate": (
            "Ensure account lockout is enforced via pam_faillock in the RHEL PAM stacks.\n"
            "```\n"
            "# grep -P 'pam_faillock\\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth\n"
            "# grep -P '^\\h*(deny|unlock_time)' /etc/security/faillock.conf\n"
            "```"
        ),
        "configure": (
            "Enable lockout via authselect + faillock.conf:\n"
            "```\n"
            "# authselect enable-feature with-faillock\n"
            "# authselect apply-changes\n"
            "# printf 'deny = 5\\nunlock_time = 900\\n' >> /etc/security/faillock.conf\n"
            "```"
        ),
    },
    "JR2.C.4.4.4": {
        "validate": (
            "Ensure password reuse is limited via pam_pwhistory in the RHEL PAM stacks.\n"
            "```\n"
            "# grep -P 'pam_pwhistory\\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth\n"
            "```\n"
            "A `remember=` option (e.g. remember=5) must be present."
        ),
        "configure": (
            "Enable password history via authselect:\n"
            "```\n"
            "# authselect enable-feature with-pwhistory\n"
            "# authselect apply-changes\n"
            "```\n"
            "Set `remember = 5` in /etc/security/pwhistory.conf (RHEL 9) or the pam_pwhistory line."
        ),
    },
    "JR2.C.4.5.2": {
        "validate": (
            "Ensure the password hashing algorithm is strong (yescrypt/sha512) in the RHEL stacks.\n"
            "```\n"
            "# grep -P '^\\h*ENCRYPT_METHOD' /etc/login.defs\n"
            "# grep -P 'pam_unix\\.so.*(sha512|yescrypt)' /etc/pam.d/system-auth /etc/pam.d/password-auth\n"
            "```"
        ),
        "configure": (
            "Set a strong hashing algorithm (RHEL 9 defaults to yescrypt):\n"
            "```\n"
            "# sed -ri 's/^ENCRYPT_METHOD.*/ENCRYPT_METHOD SHA512/' /etc/login.defs\n"
            "# authselect apply-changes\n"
            "```"
        ),
    },
}


def derive_redhat(control_id: str, field: str, debian_text: str) -> tuple[str, str]:
    """Derive Red Hat guidance for one field ("validate"|"configure") of one control.

    Precedence, most authoritative first:
      1. CIS AlmaLinux 8 authoring (``cis_alma8.ALMA8``) — real RHEL-family audit
         and remediation procedures for the controls that genuinely diverge from
         Debian (packages via rpm/dnf, firewalld, GDM, chrony, sysctl scripts) or
         that have no RHEL analogue (marked N/A → the scan skips them).
      2. Family-neutral copy — when this field's Debian procedure uses no
         Debian-only tooling (sysctl/systemctl/chmod/grep on /etc), the exact same
         commands run on RHEL, so the Red Hat cell IS the Debian cell.
      3. Not-applicable — a Debian-specific field with no AlmaLinux mapping is
         marked N/A on RHEL rather than executed (never runs apt/dpkg on RHEL).

    Returns ``(text, provenance)``.
    """
    src = (debian_text or "").strip()
    if not src:
        return "", "empty"

    entry = ALMA8.get(control_id)
    if entry is not None:
        if entry.get("na"):
            return (_NA_VALIDATE if field == "validate" else _NA_CONFIGURE), "alma-na"
        body = _fenced(entry.get(field, ""))
        prov = PROV_ALMA + f"# ({entry.get('source', 'CIS AlmaLinux 8')})\n"
        return (prov + body) if body else (PROV_NA if field == "configure" else _NA_VALIDATE), "alma"

    if not _DEB_ONLY.search(src):
        return PROV_NEUTRAL + debian_text, "neutral"

    # Debian-specific and unmapped → skip on RHEL rather than run a wrong command.
    return (_NA_VALIDATE if field == "validate" else _NA_CONFIGURE), "na"
