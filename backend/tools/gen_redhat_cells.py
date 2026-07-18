#!/usr/bin/env python3
"""
Author the Red Hat family Validate/Configure cells of the SABC Baseline
referential from the CIS AlmaLinux OS 8 Benchmark v4.0.0 control set.

Why this exists
---------------
The original Red Hat columns were mechanically derived from the Debian
guidance (apt→dnf text substitution). That left wrong package names
(`aide-common`, `avahi-daemon` …), Debian-only tools (`ufw`, `dpkg-query`)
inside Red Hat audit blocks, and prompt-line command sequences whose combined
exit status does not express compliance. Scans on RHEL/Alma nodes therefore
failed or lied, and enforcement could not converge.

What it does
------------
For every referential control this tool writes the Red Hat cells as a short
provenance banner + prose summary + ONE fenced script block:

  * scripts start with `#!/usr/bin/env bash`, so the platform's
    ``extract_shell`` keeps them verbatim (no prompt-line reassembly),
  * Validate scripts exit 0 = compliant, 1 = non-compliant,
    101 = not applicable on this node (the platform's NA convention),
  * Configure scripts are idempotent and end with a meaningful exit status,
  * checks/values follow the CIS AlmaLinux 8 v4.0.0 audit/remediation intent
    (§ references in each banner) and the referential's own Agreed Values
    (e.g. password reuse = last 5, sudo timestamp_timeout ≤ 15, TMOUT ≤ 900).

Controls that are Debian-specific by nature (ufw, apport) get
``Applies To = debian`` so the Red Hat family honestly skips them instead of
faking a check. AppArmor controls map to their SELinux equivalents (the Red
Hat family's mandatory access control) with an explicit note.

Usage:  python3 backend/tools/gen_redhat_cells.py   (rewrites the seed CSV
in place; run from the repo root or backend/).
"""
from __future__ import annotations

import csv
import os
import re
import sys

# ── locate the seed CSV ───────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
CSV_PATH = os.path.join(
    _BACKEND, "platform", "seed", "referentials", "sabc_baseline", "sabc_baseline.csv"
)

BENCH = "CIS AlmaLinux OS 8 Benchmark v4.0.0"


def banner(ref: str | None, note: str | None = None) -> str:
    if ref:
        b = f"# [SABC] Red Hat family guidance — authored from {BENCH} §{ref}."
    else:
        b = ("# [SABC] Red Hat family guidance — authored for the Red Hat family "
             f"(no direct {BENCH} equivalent).")
    if note:
        b += f"\n# [SABC] {note}"
    return b


def cell(ref: str | None, prose: str, script: str | None, note: str | None = None) -> str:
    """Assemble a referential cell: banner, prose, and the fenced script."""
    parts = [banner(ref, note)]
    if prose:
        parts.append(prose.strip())
    if script:
        body = script.strip("\n")
        parts.append(f"```\n#!/usr/bin/env bash\n{body}\n```")
    return "\n".join(parts) + "\n"


# ── script builders (validate: 0 ok / 1 fail / 101 N-A) ──────────────────────

def v_kmod(mod: str) -> str:
    return f"""\
# Compliant when the {mod} kernel module cannot be loaded and is not loaded.
lsmod | grep -q '^{mod}\\b' && exit 1
out=$(modprobe -n -v {mod} 2>/dev/null)
[ -z "$out" ] && exit 0                     # not available in this kernel
echo "$out" | grep -Eq '(^|/bin/)(true|false)' && exit 0
exit 1"""


def c_kmod(mod: str) -> str:
    return f"""\
printf 'install {mod} /bin/false\\nblacklist {mod}\\n' > /etc/modprobe.d/{mod}.conf
modprobe -r {mod} 2>/dev/null || true
exit 0"""


def v_mntopt(mount: str, opt: str) -> str:
    return f"""\
# N/A when {mount} is not a separate mount point on this node.
findmnt -kn {mount} >/dev/null 2>&1 || exit 101
findmnt -kn {mount} | grep -qw {opt}"""


def c_mntopt(mount: str, opt: str) -> str:
    esc = mount.replace("/", r"\/")
    return f"""\
findmnt -kn {mount} >/dev/null 2>&1 || exit 0
if grep -Eq '^[^#]+\\s{esc}\\s' /etc/fstab; then
  grep -E '^[^#]+\\s{esc}\\s' /etc/fstab | grep -qw {opt} || \\
    sed -ri 's|^([^#]+\\s{esc}\\s+\\S+\\s+)([^[:space:]]+)|\\1\\2,{opt}|' /etc/fstab
fi
mount -o remount,{opt} {mount} 2>/dev/null || mount -o remount {mount}"""


def v_pkg_absent(pkgs: list[str], units: list[str] | None = None) -> str:
    """Not-in-use check: package absent, or (if a dependency) units inert."""
    pl = " ".join(pkgs)
    if not units:
        return f"""\
for p in {pl}; do
  rpm -q "$p" >/dev/null 2>&1 && exit 1
done
exit 0"""
    ul = " ".join(units)
    return f"""\
installed=0
for p in {pl}; do rpm -q "$p" >/dev/null 2>&1 && installed=1; done
[ "$installed" -eq 0 ] && exit 0
# Package present (may be a dependency): its units must be neither enabled nor active.
systemctl is-enabled {ul} 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active {ul} 2>/dev/null | grep -q '^active' && exit 1
exit 0"""


def c_pkg_absent(pkgs: list[str], units: list[str] | None = None) -> str:
    pl = " ".join(pkgs)
    lines = []
    if units:
        lines.append(f"systemctl stop {' '.join(units)} 2>/dev/null || true")
        lines.append(f"systemctl mask {' '.join(units)} 2>/dev/null || true")
    lines.append(f"dnf remove -y {pl}")
    return "\n".join(lines)


def v_pkg_present(pkgs: list[str]) -> str:
    pl = " ".join(pkgs)
    return f"""\
for p in {pl}; do
  rpm -q "$p" >/dev/null 2>&1 || exit 1
done
exit 0"""


def c_pkg_present(pkgs: list[str], post: str = "") -> str:
    s = f"dnf install -y {' '.join(pkgs)}"
    if post:
        s += "\n" + post
    return s


def v_sysctl(pairs: dict[str, str], ipv6_guard: bool = False) -> str:
    lines = []
    if ipv6_guard:
        first = next(iter(pairs))
        lines.append(f"# N/A when IPv6 is disabled on this node (key absent).")
        lines.append(f"sysctl -n {first} >/dev/null 2>&1 || exit 101")
    for k, want in pairs.items():
        lines.append(f'[ "$(sysctl -n {k} 2>/dev/null)" = "{want}" ] || exit 1')
    lines.append("exit 0")
    return "\n".join(lines)


def c_sysctl(slug: str, pairs: dict[str, str], flush: bool = False,
             ipv6_guard: bool = False) -> str:
    conf = f"/etc/sysctl.d/60-criclo-{slug}.conf"
    lines = []
    if ipv6_guard:
        first = next(iter(pairs))
        lines.append(f"sysctl -n {first} >/dev/null 2>&1 || exit 0")
    body = "\\n".join(f"{k} = {v}" for k, v in pairs.items())
    lines.append(f"printf '{body}\\n' > {conf}")
    for k, v in pairs.items():
        lines.append(f"sysctl -w {k}={v}")
    if flush:
        lines.append("sysctl -w net.ipv4.route.flush=1")
        if any(k.startswith("net.ipv6") for k in pairs):
            lines.append("sysctl -w net.ipv6.route.flush=1 2>/dev/null || true")
    return "\n".join(lines)


def v_perm(path: str, maxmode: str, owner: str = "root", group: str = "root",
           missing_ok: bool = True, groups: tuple[str, ...] = ()) -> str:
    """Mode is a maximum (no bit beyond *maxmode*); owner/group exact
    (*groups* allows alternatives, e.g. root|ssh_keys for host keys)."""
    miss = "exit 0" if missing_ok else "exit 1"
    gset = groups or (group,)
    gtest = " || ".join(f'[ "$g" = "{gg}" ]' for gg in gset)
    return f"""\
f={path}
[ -e "$f" ] || {miss}
set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
[ "$o" = "{owner}" ] || exit 1
{{ {gtest}; }} || exit 1
[ $(( 8#$m & ~8#{maxmode} & 8#7777 )) -eq 0 ] || exit 1
exit 0"""


def c_perm(path: str, mode: str, owner: str = "root", group: str = "root") -> str:
    return f"""\
f={path}
[ -e "$f" ] || exit 0
chown {owner}:{group} "$f"
chmod {mode} "$f\""""


def v_sshd(cond: str, comment: str = "") -> str:
    """Check a value from the effective sshd config (sshd -T)."""
    pre = f"# {comment}\n" if comment else ""
    return f"""\
{pre}command -v sshd >/dev/null 2>&1 || exit 101
T=$(sshd -T 2>/dev/null) || exit 1
{cond}"""


def c_sshd(param: str, value: str) -> str:
    """Set an sshd_config directive (drop-in when supported, else in place).
    Never restarts sshd — reload only, and only with a valid config."""
    return f"""\
cfg=/etc/ssh/sshd_config
if grep -Eiq '^\\s*Include\\s+/etc/ssh/sshd_config.d' "$cfg" && [ -d /etc/ssh/sshd_config.d ]; then
  printf '{param} {value}\\n' > /etc/ssh/sshd_config.d/60-criclo-{param.lower()}.conf
else
  sed -ri 's/^\\s*#?\\s*{param}\\b.*/{param} {value}/I' "$cfg"
  grep -Eiq '^\\s*{param}\\b' "$cfg" || printf '{param} {value}\\n' >> "$cfg"
fi
sshd -t || exit 1
systemctl reload sshd 2>/dev/null || true
exit 0"""


def v_svc_inert(units: list[str], na_pkg: str | None = None) -> str:
    ul = " ".join(units)
    guard = (f"rpm -q {na_pkg} >/dev/null 2>&1 || exit 101\n" if na_pkg else "")
    return f"""\
{guard}systemctl is-enabled {ul} 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active {ul} 2>/dev/null | grep -q '^active' && exit 1
exit 0"""


def c_svc_inert(units: list[str]) -> str:
    ul = " ".join(units)
    return f"""\
systemctl stop {ul} 2>/dev/null || true
systemctl mask {ul} 2>/dev/null || true
exit 0"""


def v_logindefs(key: str, test: str) -> str:
    """Check a /etc/login.defs value; *test* is a shell condition on $v."""
    return f"""\
v=$(awk '/^\\s*{key}\\b/ {{print $2}}' /etc/login.defs)
[ -n "$v" ] || exit 1
{test}"""


def c_logindefs(key: str, value: str, chage_flag: str | None = None) -> str:
    lines = [
        f"sed -ri 's/^\\s*#?\\s*{key}\\b.*/{key} {value}/' /etc/login.defs",
        f"grep -Eq '^\\s*{key}\\b' /etc/login.defs || printf '{key} {value}\\n' >> /etc/login.defs",
    ]
    if chage_flag:
        # Applies to every account with a real password, root included — the
        # CIS remediation does the same, and excluding root would leave the
        # validate check failing forever.
        lines.append(
            "awk -F: '($2!~/^[!*]/) {print $1}' /etc/shadow | "
            f"while read -r u; do chage {chage_flag} {value} \"$u\"; done"
        )
    return "\n".join(lines)


def v_pwquality(key: str, test: str) -> str:
    return f"""\
rpm -q libpwquality >/dev/null 2>&1 || exit 1
v=$(awk -F= '/^\\s*{key}\\s*=/ {{gsub(/ /,"",$2); print $2}}' \\
    /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -n1)
[ -n "$v" ] || exit 1
{test}"""


def c_pwquality(key: str, value: str) -> str:
    return f"""\
mkdir -p /etc/security/pwquality.conf.d
printf '{key} = {value}\\n' > /etc/security/pwquality.conf.d/60-criclo-{key}.conf
exit 0"""


# ── the per-control specification ────────────────────────────────────────────
# cid → dict(ref=alma §, prose=…, v=validate script, c=configure script | None,
#            debian_only=True, note=…)

S: dict[str, dict] = {}

# ---- 1.1 filesystems -------------------------------------------------------
S["JR2.C.1.1.1"] = dict(
    ref="2.1.1", prose="Verify the autofs automounter is not in use.",
    v=v_pkg_absent(["autofs"], ["autofs.service"]),
    c=c_pkg_absent(["autofs"], ["autofs.service"]))
S["JR2.C.1.1.2"] = dict(
    ref="1.1.1.10", prose="Verify the usb-storage kernel module is not available.",
    v=v_kmod("usb-storage"), c=c_kmod("usb-storage"))
for cid, mod, ref in [
    ("JR2.C.1.1.1.1", "cramfs", "1.1.1.1"), ("JR2.C.1.1.1.2", "freevxfs", "1.1.1.2"),
    ("JR2.C.1.1.1.3", "jffs2", "1.1.1.5"), ("JR2.C.1.1.1.4", "hfs", "1.1.1.3"),
    ("JR2.C.1.1.1.5", "hfsplus", "1.1.1.4"),
]:
    S[cid] = dict(ref=ref, prose=f"Verify the {mod} kernel module is not available.",
                  v=v_kmod(mod), c=c_kmod(mod))

S["JR2.C.1.1.2.1"] = dict(
    ref="1.1.2.1.1", prose="Verify /tmp is tmpfs or a separate partition.",
    v="findmnt -kn /tmp >/dev/null 2>&1",
    c="""\
systemctl unmask tmp.mount 2>/dev/null || true
systemctl enable --now tmp.mount""")

for cid, mnt, opt, ref in [
    ("JR2.C.1.1.2.2", "/tmp", "nodev", "1.1.2.1.2"),
    ("JR2.C.1.1.2.3", "/tmp", "noexec", "1.1.2.1.4"),
    ("JR2.C.1.1.2.4", "/tmp", "nosuid", "1.1.2.1.3"),
    ("JR2.C.1.1.3.1", "/var", "nodev", "1.1.2.4.2"),
    ("JR2.C.1.1.3.2", "/var", "nosuid", "1.1.2.4.3"),
    ("JR2.C.1.1.4.1", "/var/tmp", "nodev", "1.1.2.5.2"),
    ("JR2.C.1.1.4.2", "/var/tmp", "noexec", "1.1.2.5.4"),
    ("JR2.C.1.1.4.3", "/var/tmp", "nosuid", "1.1.2.5.3"),
    ("JR2.C.1.1.5.1", "/var/log", "nodev", "1.1.2.6.2"),
    ("JR2.C.1.1.5.2", "/var/log", "noexec", "1.1.2.6.4"),
    ("JR2.C.1.1.5.3", "/var/log", "nosuid", "1.1.2.6.3"),
    ("JR2.C.1.1.6.1", "/var/log/audit", "nodev", "1.1.2.7.2"),
    ("JR2.C.1.1.6.2", "/var/log/audit", "noexec", "1.1.2.7.4"),
    ("JR2.C.1.1.6.3", "/var/log/audit", "nosuid", "1.1.2.7.3"),
    ("JR2.C.1.1.7.1", "/home", "nodev", "1.1.2.3.2"),
    ("JR2.C.1.1.7.2", "/home", "nosuid", "1.1.2.3.3"),
    ("JR2.C.1.1.8.1", "/dev/shm", "nodev", "1.1.2.2.2"),
    ("JR2.C.1.1.8.2", "/dev/shm", "noexec", "1.1.2.2.4"),
    ("JR2.C.1.1.8.3", "/dev/shm", "nosuid", "1.1.2.2.3"),
]:
    S[cid] = dict(ref=ref, prose=f"Verify the {opt} option is set on the {mnt} mount.",
                  v=v_mntopt(mnt, opt), c=c_mntopt(mnt, opt))

# ---- 1.2 AIDE --------------------------------------------------------------
S["JR2.C.1.2.1"] = dict(
    ref="6.1.1", prose="Verify AIDE is installed (the EL package is `aide`; "
    "there is no aide-common on the Red Hat family).",
    v=v_pkg_present(["aide"]),
    c="""\
dnf install -y aide
if [ ! -f /var/lib/aide/aide.db.gz ]; then
  aide --init && mv -f /var/lib/aide/aide.db.new.gz /var/lib/aide/aide.db.gz
fi
exit 0""")
S["JR2.C.1.2.2"] = dict(
    ref="6.1.2", prose="Verify a periodic AIDE filesystem-integrity check is scheduled.",
    v="""\
rpm -q aide >/dev/null 2>&1 || exit 1
grep -Ersq '^([^#]+\\s)?(/usr/sbin/)?aide(\\.wrapper)?\\s(--check|.*--check)' \\
  /etc/cron.d /etc/cron.daily /etc/cron.weekly /etc/crontab /var/spool/cron 2>/dev/null && exit 0
systemctl is-enabled aidecheck.timer 2>/dev/null | grep -q enabled && exit 0
exit 1""",
    c="""\
printf '0 5 * * * root /usr/sbin/aide --check\\n' > /etc/cron.d/aide-check
chmod 600 /etc/cron.d/aide-check""")

# ---- 1.3 bootloader --------------------------------------------------------
S["JR2.C.1.3.1"] = dict(
    ref="1.4.1", prose="Verify a bootloader password is set (grub2 user.cfg).\n"
    "Setting the password requires the operator to run `grub2-setpassword` "
    "interactively; it cannot be authored unattended.",
    v="""\
for f in /boot/grub2/user.cfg /boot/efi/EFI/*/user.cfg; do
  [ -f "$f" ] && grep -q '^GRUB2_PASSWORD=grub\\.pbkdf2' "$f" && exit 0
done
exit 1""",
    c=None)
S["JR2.C.1.3.2"] = dict(
    ref="1.4.2", prose="Verify access to the bootloader configuration is restricted to root.",
    v="""\
ok=0
for f in /boot/grub2/grub.cfg /boot/grub2/grubenv /boot/grub2/user.cfg; do
  [ -e "$f" ] || continue
  ok=1
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ "$o" = root ] && [ "$g" = root ] || exit 1
  [ $(( 8#$m & 8#0077 )) -eq 0 ] || exit 1
done
[ "$ok" -eq 1 ] && exit 0 || exit 101""",
    c="""\
for f in /boot/grub2/grub.cfg /boot/grub2/grubenv /boot/grub2/user.cfg; do
  [ -e "$f" ] || continue
  chown root:root "$f"
  chmod u-x,go-rwx "$f"
done
exit 0""")
S["JR2.C.1.3.3"] = dict(
    ref=None, prose="Verify rescue and emergency mode require authentication "
    "(systemd-sulogin-shell, the EL default).",
    v="""\
grep -Eq 'sulogin' /usr/lib/systemd/system/rescue.service /etc/systemd/system/rescue.service.d/*.conf 2>/dev/null || exit 1
grep -Eq 'sulogin' /usr/lib/systemd/system/emergency.service /etc/systemd/system/emergency.service.d/*.conf 2>/dev/null || exit 1
exit 0""",
    c=None)

# ---- 1.4 hardening ---------------------------------------------------------
S["JR2.C.1.4.1"] = dict(
    ref=None, prose="Verify prelink is not installed (not shipped with EL 8; "
    "must stay absent).",
    v=v_pkg_absent(["prelink"]),
    c="""\
command -v prelink >/dev/null 2>&1 && prelink -ua 2>/dev/null || true
dnf remove -y prelink""")
S["JR2.C.1.4.2"] = dict(
    ref="1.5.8", prose="Verify address space layout randomization is enabled "
    "(kernel.randomize_va_space = 2).",
    v=v_sysctl({"kernel.randomize_va_space": "2"}),
    c=c_sysctl("aslr", {"kernel.randomize_va_space": "2"}))
S["JR2.C.1.4.3"] = dict(
    ref="1.5.7", prose="Verify ptrace is restricted (kernel.yama.ptrace_scope ≥ 1).",
    v="""\
v=$(sysctl -n kernel.yama.ptrace_scope 2>/dev/null)
[ -n "$v" ] && [ "$v" -ge 1 ] && [ "$v" -le 3 ]""",
    c=c_sysctl("ptrace", {"kernel.yama.ptrace_scope": "1"}))
S["JR2.C.1.4.4"] = dict(debian_only=True)   # apport is Ubuntu-specific
S["JR2.C.1.4.5"] = dict(
    ref="1.5.1", prose="Verify core dumps are restricted (hard limit 0, "
    "fs.suid_dumpable = 0, and systemd-coredump storage off when present).",
    v="""\
grep -Ersq '^\\s*\\*\\s+hard\\s+core\\s+0\\b' /etc/security/limits.conf /etc/security/limits.d 2>/dev/null || exit 1
[ "$(sysctl -n fs.suid_dumpable 2>/dev/null)" = "0" ] || exit 1
if rpm -q systemd-coredump >/dev/null 2>&1; then
  grep -Ersq '^\\s*Storage\\s*=\\s*none' /etc/systemd/coredump.conf /etc/systemd/coredump.conf.d 2>/dev/null || exit 1
fi
exit 0""",
    c="""\
printf '* hard core 0\\n' > /etc/security/limits.d/60-criclo-core.conf
printf 'fs.suid_dumpable = 0\\n' > /etc/sysctl.d/60-criclo-coredump.conf
sysctl -w fs.suid_dumpable=0
if rpm -q systemd-coredump >/dev/null 2>&1; then
  mkdir -p /etc/systemd/coredump.conf.d
  printf '[Coredump]\\nStorage=none\\nProcessSizeMax=0\\n' > /etc/systemd/coredump.conf.d/60-criclo.conf
fi
exit 0""")

# ---- 1.5 MAC (AppArmor ↔ SELinux) ------------------------------------------
_selinux_note = ("On the Red Hat family the mandatory access control system is "
                 "SELinux; this is the SELinux equivalent of the AppArmor control.")
S["JR2.C.1.5.1"] = dict(
    ref="1.3.1.1", note=_selinux_note,
    prose="Verify SELinux is installed.",
    v=v_pkg_present(["libselinux"]), c=c_pkg_present(["libselinux"]))
S["JR2.C.1.5.2"] = dict(
    ref="1.3.1.2", note=_selinux_note,
    prose="Verify SELinux is not disabled in the bootloader configuration.",
    v="""\
command -v grubby >/dev/null 2>&1 || exit 101
grubby --info=ALL 2>/dev/null | grep -Eq '(selinux=0|enforcing=0)' && exit 1
exit 0""",
    c="""\
command -v grubby >/dev/null 2>&1 || exit 0
grubby --update-kernel ALL --remove-args 'selinux=0 enforcing=0'""")
S["JR2.C.1.5.3"] = dict(
    ref="1.3.1.5", note=_selinux_note,
    prose="Verify SELinux is active — Enforcing, or at minimum Permissive "
    "(the analogue of AppArmor enforce/complain).",
    v="""\
command -v getenforce >/dev/null 2>&1 || exit 1
m=$(getenforce)
[ "$m" = "Enforcing" ] || [ "$m" = "Permissive" ]""",
    c="""\
sed -ri 's/^\\s*SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
setenforce 1 2>/dev/null || true
exit 0""")

# ---- 1.6 banners -----------------------------------------------------------
def _v_banner(path: str) -> str:
    return f"""\
f={path}
[ -e "$f" ] || exit 0
grep -Eiq '(\\\\v|\\\\r|\\\\m|\\\\s)' "$f" && exit 1
for tok in $(. /etc/os-release; echo "$ID"); do
  grep -iq "$tok" "$f" && exit 1
done
exit 0"""

def _c_banner(path: str) -> str:
    return f"""\
printf 'Authorized users only. All activity may be monitored and reported.\\n' > {path}
chown root:root {path}
chmod u-x,go-wx {path}"""

S["JR2.C.1.6.1"] = dict(ref="1.7.1", prose="Verify /etc/motd leaks no OS or version information.",
                        v=_v_banner("/etc/motd"), c=_c_banner("/etc/motd"))
S["JR2.C.1.6.2"] = dict(ref="1.7.2", prose="Verify /etc/issue leaks no OS or version information.",
                        v=_v_banner("/etc/issue"), c=_c_banner("/etc/issue"))
S["JR2.C.1.6.3"] = dict(ref="1.7.3", prose="Verify /etc/issue.net leaks no OS or version information.",
                        v=_v_banner("/etc/issue.net"), c=_c_banner("/etc/issue.net"))
S["JR2.C.1.6.4"] = dict(ref="1.7.4", prose="Verify access to /etc/motd is configured (644 root:root).",
                        v=v_perm("/etc/motd", "644"), c=c_perm("/etc/motd", "644"))
S["JR2.C.1.6.5"] = dict(ref="1.7.5", prose="Verify access to /etc/issue is configured (644 root:root).",
                        v=v_perm("/etc/issue", "644"), c=c_perm("/etc/issue", "644"))
S["JR2.C.1.6.6"] = dict(ref="1.7.6", prose="Verify access to /etc/issue.net is configured (644 root:root).",
                        v=v_perm("/etc/issue.net", "644"), c=c_perm("/etc/issue.net", "644"))

# ---- 1.7 GDM ---------------------------------------------------------------
_GDM_NA = "rpm -q gdm >/dev/null 2>&1 || exit 101"

def _v_dconf(keyfile_grep: str, lock_grep: str | None = None) -> str:
    s = f"""\
{_GDM_NA}
grep -Ersq '{keyfile_grep}' /etc/dconf/db/*.d 2>/dev/null || exit 1"""
    if lock_grep:
        s += f"""
grep -Ersq '{lock_grep}' /etc/dconf/db/*.d/locks 2>/dev/null || exit 1"""
    return s + "\nexit 0"

def _c_dconf(db: str, section: str, kv: list[str], locks: list[str]) -> str:
    body = "\\n".join([f"[{section}]"] + kv)
    lockbody = "\\n".join(locks)
    return f"""\
rpm -q gdm >/dev/null 2>&1 || exit 0
mkdir -p /etc/dconf/db/{db}.d/locks /etc/dconf/profile
grep -q '^system-db:{db}$' /etc/dconf/profile/user 2>/dev/null || {{
  printf 'user-db:user\\nsystem-db:{db}\\n' > /etc/dconf/profile/user
}}
printf '{body}\\n' > /etc/dconf/db/{db}.d/60-criclo
printf '{lockbody}\\n' > /etc/dconf/db/{db}.d/locks/60-criclo
dconf update"""

S["JR2.C.1.7.1"] = dict(
    ref="1.8.1", prose="Verify the GDM login banner is configured (N/A when GDM is not installed).",
    v=_v_dconf(r"^\s*banner-message-enable\s*=\s*true"),
    c=_c_dconf("gdm", "org/gnome/login-screen",
               ["banner-message-enable=true",
                "banner-message-text='Authorized users only. All activity may be monitored and reported.'"],
               ["/org/gnome/login-screen/banner-message-enable"]))
S["JR2.C.1.7.2"] = dict(
    ref="1.8.2", prose="Verify the GDM user list is disabled (N/A when GDM is not installed).",
    v=_v_dconf(r"^\s*disable-user-list\s*=\s*true"),
    c=_c_dconf("gdm", "org/gnome/login-screen", ["disable-user-list=true"],
               ["/org/gnome/login-screen/disable-user-list"]))
S["JR2.C.1.7.3"] = dict(
    ref="1.8.3", prose="Verify the GDM screen locks when idle (N/A when GDM is not installed).",
    v=_v_dconf(r"^\s*idle-delay\s*=\s*uint32\s+[1-9]"),
    c=_c_dconf("local", "org/gnome/desktop/session", ["idle-delay=uint32 900"],
               ["/org/gnome/desktop/session/idle-delay"]))
S["JR2.C.1.7.4"] = dict(
    ref="1.8.3", prose="Verify the idle screen-lock settings are locked against user override.",
    v=_v_dconf(r"^\s*idle-delay\s*=\s*uint32\s+[1-9]",
               r"/org/gnome/desktop/session/idle-delay"),
    c=_c_dconf("local", "org/gnome/desktop/screensaver", ["lock-delay=uint32 5"],
               ["/org/gnome/desktop/session/idle-delay",
                "/org/gnome/desktop/screensaver/lock-delay"]))
S["JR2.C.1.7.5"] = dict(
    ref="1.8.4", prose="Verify GDM automatic mounting of removable media is disabled.",
    v=_v_dconf(r"^\s*automount(-open)?\s*=\s*false"),
    c=_c_dconf("local", "org/gnome/desktop/media-handling",
               ["automount=false", "automount-open=false"],
               ["/org/gnome/desktop/media-handling/automount",
                "/org/gnome/desktop/media-handling/automount-open"]))
S["JR2.C.1.7.6"] = dict(
    ref="1.8.4", prose="Verify the automount-off settings are locked against user override.",
    v=_v_dconf(r"^\s*automount(-open)?\s*=\s*false",
               r"/org/gnome/desktop/media-handling/automount"),
    c=_c_dconf("local", "org/gnome/desktop/media-handling",
               ["automount=false", "automount-open=false"],
               ["/org/gnome/desktop/media-handling/automount",
                "/org/gnome/desktop/media-handling/automount-open"]))
S["JR2.C.1.7.7"] = dict(
    ref="1.8.5", prose="Verify GDM autorun-never is enabled.",
    v=_v_dconf(r"^\s*autorun-never\s*=\s*true"),
    c=_c_dconf("local", "org/gnome/desktop/media-handling", ["autorun-never=true"],
               ["/org/gnome/desktop/media-handling/autorun-never"]))
S["JR2.C.1.7.8"] = dict(
    ref="1.8.5", prose="Verify autorun-never is locked against user override.",
    v=_v_dconf(r"^\s*autorun-never\s*=\s*true",
               r"/org/gnome/desktop/media-handling/autorun-never"),
    c=_c_dconf("local", "org/gnome/desktop/media-handling", ["autorun-never=true"],
               ["/org/gnome/desktop/media-handling/autorun-never"]))
S["JR2.C.1.7.9"] = dict(
    ref="1.8.6", prose="Verify XDMCP is not enabled in GDM (N/A when GDM is not installed).",
    v=f"""\
{_GDM_NA}
[ -f /etc/gdm/custom.conf ] || exit 0
awk '/^\\[xdmcp\\]/{{f=1;next}} /^\\[/{{f=0}} f && /^\\s*Enable\\s*=\\s*true/{{found=1}} END{{exit found?1:0}}' /etc/gdm/custom.conf""",
    c="""\
rpm -q gdm >/dev/null 2>&1 || exit 0
[ -f /etc/gdm/custom.conf ] || exit 0
sed -ri '/^\\[xdmcp\\]/,/^\\[/ s/^\\s*Enable\\s*=\\s*true/#Enable=false/' /etc/gdm/custom.conf""")

# ---- 2.1 time synchronisation ----------------------------------------------
S["JR2.C.2.1.1.1"] = dict(
    ref="2.3.1", prose="Verify exactly one time-synchronisation daemon is in use "
    "(chrony is the EL default).",
    v="""\
n=0
systemctl is-enabled chronyd.service 2>/dev/null | grep -q enabled && n=$((n+1))
systemctl is-enabled ntpd.service 2>/dev/null | grep -q enabled && n=$((n+1))
systemctl is-enabled systemd-timesyncd.service 2>/dev/null | grep -q enabled && n=$((n+1))
[ "$n" -eq 1 ]""",
    c="""\
dnf install -y chrony
systemctl stop ntpd.service systemd-timesyncd.service 2>/dev/null || true
systemctl mask ntpd.service systemd-timesyncd.service 2>/dev/null || true
systemctl unmask chronyd.service 2>/dev/null || true
systemctl enable --now chronyd.service""")
S["JR2.C.2.1.2.1"] = dict(
    ref="2.3.3", prose="Verify chronyd does not run as root (the EL service user is "
    "`chrony`, not Debian's `_chrony`).",
    v="""\
rpm -q chrony >/dev/null 2>&1 || exit 101
pgrep -u root -x chronyd >/dev/null 2>&1 && exit 1
exit 0""",
    c="""\
rpm -q chrony >/dev/null 2>&1 || exit 0
if ! grep -Eq '^\\s*OPTIONS=.*-u\\s+chrony' /etc/sysconfig/chronyd 2>/dev/null; then
  printf 'OPTIONS="-u chrony"\\n' > /etc/sysconfig/chronyd
fi
systemctl try-restart chronyd.service 2>/dev/null || true
exit 0""")
S["JR2.C.2.1.2.2"] = dict(
    ref="2.3.2", prose="Verify chrony is enabled and running.",
    v="""\
rpm -q chrony >/dev/null 2>&1 || exit 101
systemctl is-enabled chronyd.service 2>/dev/null | grep -q enabled || exit 1
systemctl is-active chronyd.service 2>/dev/null | grep -q '^active' || exit 1
exit 0""",
    c="""\
rpm -q chrony >/dev/null 2>&1 || dnf install -y chrony
systemctl unmask chronyd.service 2>/dev/null || true
systemctl enable --now chronyd.service""")
S["JR2.C.2.1.3.1"] = dict(
    ref=None, prose="systemd-timesyncd is not shipped with EL 8 — the control is "
    "not applicable unless the unit exists.",
    v="""\
systemctl list-unit-files systemd-timesyncd.service 2>/dev/null | grep -q systemd-timesyncd || exit 101
grep -Ersq '^\\s*NTP=\\S+' /etc/systemd/timesyncd.conf /etc/systemd/timesyncd.conf.d 2>/dev/null""",
    c="""\
systemctl list-unit-files systemd-timesyncd.service 2>/dev/null | grep -q systemd-timesyncd || exit 0
mkdir -p /etc/systemd/timesyncd.conf.d
printf '[Time]\\nNTP=pool.ntp.org\\n' > /etc/systemd/timesyncd.conf.d/60-criclo.conf
systemctl try-restart systemd-timesyncd.service 2>/dev/null || true
exit 0""")
_NTP_NA = "rpm -q ntp >/dev/null 2>&1 || exit 101"
S["JR2.C.2.1.4.1"] = dict(
    ref=None, prose="ntp is not shipped with EL 8 (chrony replaces it) — N/A unless installed.",
    v=f"""\
{_NTP_NA}
c=$(grep -Ec '^\\s*restrict\\s+(-4\\s+|-6\\s+)?default\\s' /etc/ntp.conf 2>/dev/null)
[ "$c" -ge 2 ]""",
    c=f"""\
{_NTP_NA.replace('exit 101', 'exit 0')}
grep -Eq '^\\s*restrict\\s+(-4\\s+)?default' /etc/ntp.conf || \\
  printf 'restrict -4 default kod nomodify notrap nopeer noquery\\n' >> /etc/ntp.conf
grep -Eq '^\\s*restrict\\s+-6\\s+default' /etc/ntp.conf || \\
  printf 'restrict -6 default kod nomodify notrap nopeer noquery\\n' >> /etc/ntp.conf
systemctl try-restart ntpd.service 2>/dev/null || true
exit 0""")
S["JR2.C.2.1.4.2"] = dict(
    ref=None, prose="ntp is not shipped with EL 8 — N/A unless installed.",
    v=f"""\
{_NTP_NA}
pgrep -x ntpd >/dev/null 2>&1 || exit 101
pgrep -u root -x ntpd >/dev/null 2>&1 && exit 1
exit 0""",
    c=None)
S["JR2.C.2.1.4.3"] = dict(
    ref=None, prose="ntp is not shipped with EL 8 — N/A unless installed.",
    v=f"""\
{_NTP_NA}
systemctl is-enabled ntpd.service 2>/dev/null | grep -q enabled || exit 1
systemctl is-active ntpd.service 2>/dev/null | grep -q '^active' || exit 1
exit 0""",
    c=f"""\
{_NTP_NA.replace('exit 101', 'exit 0')}
systemctl unmask ntpd.service 2>/dev/null || true
systemctl enable --now ntpd.service""")

# ---- 2.2 server services ---------------------------------------------------
def _svc(cid, ref, what, pkgs, units):
    S[cid] = dict(ref=ref, prose=f"Verify {what} is not in use (package absent, "
                  "or its units neither enabled nor active).",
                  v=v_pkg_absent(pkgs, units), c=c_pkg_absent(pkgs, units))

_svc("JR2.C.2.2.1", "2.1.2", "the Avahi server", ["avahi"],
     ["avahi-daemon.socket", "avahi-daemon.service"])
_svc("JR2.C.2.2.2", "2.1.11", "the CUPS print server", ["cups"],
     ["cups.socket", "cups.service"])
_svc("JR2.C.2.2.3", "2.1.4", "the DHCP server", ["dhcp-server"],
     ["dhcpd.service", "dhcpd6.service"])
_svc("JR2.C.2.2.4", None, "the OpenLDAP server", ["openldap-servers"],
     ["slapd.service"])
_svc("JR2.C.2.2.5", "2.1.9", "the NFS server", ["nfs-utils"],
     ["nfs-server.service"])
_svc("JR2.C.2.2.6", "2.1.5", "the DNS server", ["bind"], ["named.service"])
_svc("JR2.C.2.2.7", "2.1.7", "the FTP server", ["vsftpd"], ["vsftpd.service"])
_svc("JR2.C.2.2.8", "2.1.19", "a web server", ["httpd", "nginx"],
     ["httpd.socket", "httpd.service", "nginx.service"])
_svc("JR2.C.2.2.9", "2.1.8", "an IMAP/POP3 server", ["dovecot", "cyrus-imapd"],
     ["dovecot.socket", "dovecot.service", "cyrus-imapd.service"])
_svc("JR2.C.2.2.10", "2.1.14", "the Samba file server", ["samba"], ["smb.service"])
_svc("JR2.C.2.2.11", "2.1.18", "the Squid web proxy", ["squid"], ["squid.service"])
_svc("JR2.C.2.2.12", "2.1.15", "the SNMP server", ["net-snmp"], ["snmpd.service"])
_svc("JR2.C.2.2.13", "2.1.10", "the NIS server", ["ypserv"], ["ypserv.service"])
_svc("JR2.C.2.2.14", "2.1.6", "dnsmasq", ["dnsmasq"], ["dnsmasq.service"])
S["JR2.C.2.2.15"] = dict(
    ref="2.1.23", prose="Verify the mail transfer agent listens on loopback only.",
    v="""\
ss -lntu 2>/dev/null | awk '$5 !~ /^(127\\.0\\.0\\.1|\\[?::1\\]?):(25|465|587)$/ && $5 ~ /:(25|465|587)$/ {found=1} END {exit found?1:0}'""",
    c="""\
rpm -q postfix >/dev/null 2>&1 || exit 0
postconf -e 'inet_interfaces = loopback-only'
systemctl try-restart postfix.service 2>/dev/null || true
exit 0""")
S["JR2.C.2.2.16"] = dict(
    ref="2.1.13", prose="Verify the rsync daemon is not installed, or its units are "
    "masked/inactive.",
    v="""\
rpm -q rsync-daemon >/dev/null 2>&1 || {
  systemctl list-unit-files rsyncd.service 2>/dev/null | grep -q rsyncd || exit 0
}
systemctl is-enabled rsyncd.socket rsyncd.service 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active rsyncd.socket rsyncd.service 2>/dev/null | grep -q '^active' && exit 1
exit 0""",
    c="""\
systemctl stop rsyncd.socket rsyncd.service 2>/dev/null || true
systemctl mask rsyncd.socket rsyncd.service 2>/dev/null || true
dnf remove -y rsync-daemon 2>/dev/null || true
exit 0""")

# ---- 2.3 clients -----------------------------------------------------------
for cid, ref, what, pkgs in [
    ("JR2.C.2.3.1", "2.2.3", "the NIS client", ["ypbind"]),
    ("JR2.C.2.3.2", None, "the rsh client", ["rsh"]),
    ("JR2.C.2.3.3", None, "the talk client", ["talk"]),
    ("JR2.C.2.3.4", "2.2.4", "the telnet client", ["telnet"]),
    ("JR2.C.2.3.5", "2.2.2", "the LDAP client", ["openldap-clients"]),
]:
    S[cid] = dict(ref=ref, prose=f"Verify {what} is not installed.",
                  v=v_pkg_absent(pkgs), c=c_pkg_absent(pkgs))
_svc("JR2.C.2.3.6", "2.1.12", "the rpcbind service", ["rpcbind"],
     ["rpcbind.socket", "rpcbind.service"])

# ---- 3.1 unused interfaces -------------------------------------------------
S["JR2.C.3.1.1"] = dict(
    ref="3.1.2", prose="Verify no wireless interfaces are active (N/A on hosts "
    "without wireless hardware).",
    v="""\
ls /sys/class/net/*/wireless >/dev/null 2>&1 || exit 101
for w in /sys/class/net/*/wireless; do
  i=$(basename "$(dirname "$w")")
  ip link show "$i" 2>/dev/null | grep -q 'state UP' && exit 1
done
exit 0""",
    c="""\
ls /sys/class/net/*/wireless >/dev/null 2>&1 || exit 0
for w in /sys/class/net/*/wireless; do
  i=$(basename "$(dirname "$w")")
  ip link set "$i" down 2>/dev/null || true
  d=$(basename "$(readlink -f "/sys/class/net/$i/device/driver/module")" 2>/dev/null)
  [ -n "$d" ] && printf 'install %s /bin/false\\n' "$d" > "/etc/modprobe.d/60-criclo-$d.conf"
done
exit 0""")
S["JR2.C.3.1.2"] = dict(
    ref="3.1.3", prose="Verify bluetooth services are not in use.",
    v=v_pkg_absent(["bluez"], ["bluetooth.service"]),
    c=c_svc_inert(["bluetooth.service"]))

# ---- 3.2 / 3.3 network kernel parameters -----------------------------------
S["JR2.C.3.2.1"] = dict(
    ref="3.3.1.4", prose="Verify packet redirect sending is disabled.",
    v=v_sysctl({"net.ipv4.conf.all.send_redirects": "0",
                "net.ipv4.conf.default.send_redirects": "0"}),
    c=c_sysctl("send-redirects", {"net.ipv4.conf.all.send_redirects": "0",
                                  "net.ipv4.conf.default.send_redirects": "0"}, flush=True))
S["JR2.C.3.2.2"] = dict(
    ref="3.3.1.1", prose="Verify IP forwarding is disabled.",
    v="""\
[ "$(sysctl -n net.ipv4.ip_forward 2>/dev/null)" = "0" ] || exit 1
v6=$(sysctl -n net.ipv6.conf.all.forwarding 2>/dev/null)
[ -z "$v6" ] || [ "$v6" = "0" ] || exit 1
exit 0""",
    c="""\
printf 'net.ipv4.ip_forward = 0\\nnet.ipv6.conf.all.forwarding = 0\\n' > /etc/sysctl.d/60-criclo-forwarding.conf
sysctl -w net.ipv4.ip_forward=0
sysctl -w net.ipv6.conf.all.forwarding=0 2>/dev/null || true
sysctl -w net.ipv4.route.flush=1
exit 0""")
S["JR2.C.3.3.1"] = dict(
    ref="3.3.1.14", prose="Verify source-routed packets are not accepted.",
    v="""\
for k in net.ipv4.conf.all.accept_source_route net.ipv4.conf.default.accept_source_route; do
  [ "$(sysctl -n $k 2>/dev/null)" = "0" ] || exit 1
done
for k in net.ipv6.conf.all.accept_source_route net.ipv6.conf.default.accept_source_route; do
  v=$(sysctl -n $k 2>/dev/null); [ -z "$v" ] || [ "$v" = "0" ] || exit 1
done
exit 0""",
    c="""\
printf 'net.ipv4.conf.all.accept_source_route = 0\\nnet.ipv4.conf.default.accept_source_route = 0\\nnet.ipv6.conf.all.accept_source_route = 0\\nnet.ipv6.conf.default.accept_source_route = 0\\n' > /etc/sysctl.d/60-criclo-source-route.conf
sysctl -w net.ipv4.conf.all.accept_source_route=0
sysctl -w net.ipv4.conf.default.accept_source_route=0
sysctl -w net.ipv6.conf.all.accept_source_route=0 2>/dev/null || true
sysctl -w net.ipv6.conf.default.accept_source_route=0 2>/dev/null || true
sysctl -w net.ipv4.route.flush=1
exit 0""")
S["JR2.C.3.3.2"] = dict(
    ref="3.3.1.8", prose="Verify ICMP redirects are not accepted.",
    v="""\
for k in net.ipv4.conf.all.accept_redirects net.ipv4.conf.default.accept_redirects; do
  [ "$(sysctl -n $k 2>/dev/null)" = "0" ] || exit 1
done
for k in net.ipv6.conf.all.accept_redirects net.ipv6.conf.default.accept_redirects; do
  v=$(sysctl -n $k 2>/dev/null); [ -z "$v" ] || [ "$v" = "0" ] || exit 1
done
exit 0""",
    c="""\
printf 'net.ipv4.conf.all.accept_redirects = 0\\nnet.ipv4.conf.default.accept_redirects = 0\\nnet.ipv6.conf.all.accept_redirects = 0\\nnet.ipv6.conf.default.accept_redirects = 0\\n' > /etc/sysctl.d/60-criclo-accept-redirects.conf
sysctl -w net.ipv4.conf.all.accept_redirects=0
sysctl -w net.ipv4.conf.default.accept_redirects=0
sysctl -w net.ipv6.conf.all.accept_redirects=0 2>/dev/null || true
sysctl -w net.ipv6.conf.default.accept_redirects=0 2>/dev/null || true
sysctl -w net.ipv4.route.flush=1
exit 0""")
S["JR2.C.3.3.3"] = dict(
    ref="3.3.1.10", prose="Verify secure ICMP redirects are not accepted.",
    v=v_sysctl({"net.ipv4.conf.all.secure_redirects": "0",
                "net.ipv4.conf.default.secure_redirects": "0"}),
    c=c_sysctl("secure-redirects", {"net.ipv4.conf.all.secure_redirects": "0",
                                    "net.ipv4.conf.default.secure_redirects": "0"}, flush=True))
S["JR2.C.3.3.4"] = dict(
    ref="3.3.1.16", prose="Verify suspicious packets are logged (log_martians).",
    v=v_sysctl({"net.ipv4.conf.all.log_martians": "1",
                "net.ipv4.conf.default.log_martians": "1"}),
    c=c_sysctl("log-martians", {"net.ipv4.conf.all.log_martians": "1",
                                "net.ipv4.conf.default.log_martians": "1"}, flush=True))
S["JR2.C.3.3.5"] = dict(
    ref="3.3.1.7", prose="Verify broadcast ICMP requests are ignored.",
    v=v_sysctl({"net.ipv4.icmp_echo_ignore_broadcasts": "1"}),
    c=c_sysctl("icmp-broadcast", {"net.ipv4.icmp_echo_ignore_broadcasts": "1"}, flush=True))
S["JR2.C.3.3.6"] = dict(
    ref="3.3.1.6", prose="Verify bogus ICMP responses are ignored.",
    v=v_sysctl({"net.ipv4.icmp_ignore_bogus_error_responses": "1"}),
    c=c_sysctl("icmp-bogus", {"net.ipv4.icmp_ignore_bogus_error_responses": "1"}, flush=True))
S["JR2.C.3.3.7"] = dict(
    ref="3.3.1.12", prose="Verify reverse path filtering is enabled.",
    v=v_sysctl({"net.ipv4.conf.all.rp_filter": "1",
                "net.ipv4.conf.default.rp_filter": "1"}),
    c=c_sysctl("rp-filter", {"net.ipv4.conf.all.rp_filter": "1",
                             "net.ipv4.conf.default.rp_filter": "1"}, flush=True))
S["JR2.C.3.3.8"] = dict(
    ref="3.3.1.18", prose="Verify TCP SYN cookies are enabled.",
    v=v_sysctl({"net.ipv4.tcp_syncookies": "1"}),
    c=c_sysctl("syncookies", {"net.ipv4.tcp_syncookies": "1"}, flush=True))
S["JR2.C.3.3.9"] = dict(
    ref="3.3.2.7", prose="Verify IPv6 router advertisements are not accepted "
    "(N/A when IPv6 is disabled).",
    v=v_sysctl({"net.ipv6.conf.all.accept_ra": "0",
                "net.ipv6.conf.default.accept_ra": "0"}, ipv6_guard=True),
    c=c_sysctl("accept-ra", {"net.ipv6.conf.all.accept_ra": "0",
                             "net.ipv6.conf.default.accept_ra": "0"},
               flush=True, ipv6_guard=True))

# ---- 3.4 firewall ----------------------------------------------------------
# ufw does not exist on the Red Hat family: those controls honestly apply to
# the Debian family only.
for cid in ["JR2.C.3.4.1.1", "JR2.C.3.4.1.2", "JR2.C.3.4.1.3", "JR2.C.3.4.1.4",
            "JR2.C.3.4.1.5", "JR2.C.3.4.1.6", "JR2.C.3.4.2.2", "JR2.C.3.4.3.1.3"]:
    S[cid] = dict(debian_only=True)

_FW_ALT_NA = """\
# N/A when another firewall (firewalld) is the active choice on this node.
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 101"""

S["JR2.C.3.4.2.1"] = dict(
    ref="4.1.1", prose="Verify nftables is installed (the EL firewall backend).",
    v=v_pkg_present(["nftables"]), c=c_pkg_present(["nftables"]))
S["JR2.C.3.4.2.3"] = dict(
    ref=None, prose="Verify an nftables table exists (N/A when firewalld manages the firewall).",
    v=f"""\
{_FW_ALT_NA}
rpm -q nftables >/dev/null 2>&1 || exit 101
[ -n "$(nft list tables 2>/dev/null)" ]""",
    c="""\
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
nft list tables 2>/dev/null | grep -q . && exit 0
nft create table inet filter""")
S["JR2.C.3.4.2.4"] = dict(
    ref=None, prose="Verify nftables base chains exist (N/A when firewalld manages the firewall).",
    v=f"""\
{_FW_ALT_NA}
rpm -q nftables >/dev/null 2>&1 || exit 101
nft list ruleset 2>/dev/null | grep -Eq 'hook input' || exit 1
nft list ruleset 2>/dev/null | grep -Eq 'hook forward' || exit 1
nft list ruleset 2>/dev/null | grep -Eq 'hook output' || exit 1
exit 0""",
    c="""\
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
nft list tables 2>/dev/null | grep -q 'inet filter' || nft create table inet filter
nft list ruleset | grep -q 'hook input'   || nft create chain inet filter input   '{ type filter hook input priority 0 ; }'
nft list ruleset | grep -q 'hook forward' || nft create chain inet filter forward '{ type filter hook forward priority 0 ; }'
nft list ruleset | grep -q 'hook output'  || nft create chain inet filter output  '{ type filter hook output priority 0 ; }'
exit 0""")
S["JR2.C.3.4.2.5"] = dict(
    ref="4.1.5", prose="Verify nftables loopback traffic is configured (N/A when "
    "firewalld manages the firewall).",
    v=f"""\
{_FW_ALT_NA}
rpm -q nftables >/dev/null 2>&1 || exit 101
nft list ruleset 2>/dev/null | grep -Eq 'iif "lo" accept' || exit 1
nft list ruleset 2>/dev/null | grep -Eq 'ip saddr 127\\.0\\.0\\.0/8' || exit 1
exit 0""",
    c="""\
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
nft list ruleset | grep -q 'hook input' || exit 1
nft list ruleset | grep -Eq 'iif "lo" accept' || nft add rule inet filter input iif lo accept
nft list ruleset | grep -Eq 'ip saddr 127\\.0\\.0\\.0/8' || nft add rule inet filter input ip saddr 127.0.0.0/8 counter drop
exit 0""")
S["JR2.C.3.4.2.6"] = dict(
    ref=None, prose="Verify the nftables default policy is drop (N/A when firewalld "
    "manages the firewall).",
    v=f"""\
{_FW_ALT_NA}
rpm -q nftables >/dev/null 2>&1 || exit 101
nft list ruleset 2>/dev/null | grep -E 'hook (input|forward|output)' | grep -vq 'policy drop' && exit 1
nft list ruleset 2>/dev/null | grep -Eq 'hook input' || exit 1
exit 0""",
    c=None)
S["JR2.C.3.4.2.7"] = dict(
    ref=None, prose="Verify the nftables service is enabled (N/A when firewalld "
    "manages the firewall).",
    v=f"""\
{_FW_ALT_NA}
rpm -q nftables >/dev/null 2>&1 || exit 101
systemctl is-enabled nftables.service 2>/dev/null | grep -q enabled""",
    c="""\
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
systemctl unmask nftables.service 2>/dev/null || true
systemctl enable --now nftables.service""")
S["JR2.C.3.4.2.8"] = dict(
    ref=None, prose="Verify nftables rules are persistent — on the Red Hat family "
    "the boot ruleset lives in /etc/sysconfig/nftables.conf (N/A under firewalld).",
    v=f"""\
{_FW_ALT_NA}
rpm -q nftables >/dev/null 2>&1 || exit 101
grep -Eq '^\\s*(include|table)' /etc/sysconfig/nftables.conf 2>/dev/null""",
    c="""\
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
nft list ruleset > /etc/nftables/criclo.nft
grep -q '/etc/nftables/criclo.nft' /etc/sysconfig/nftables.conf 2>/dev/null || \\
  printf 'include "/etc/nftables/criclo.nft"\\n' >> /etc/sysconfig/nftables.conf
exit 0""")
S["JR2.C.3.4.3.1.1"] = dict(
    ref=None, prose="Verify the iptables packages are installed (EL: iptables + "
    "iptables-services; N/A when firewalld or nftables is the active choice).",
    v=f"""\
{_FW_ALT_NA}
systemctl is-enabled nftables.service 2>/dev/null | grep -q enabled && exit 101
rpm -q iptables iptables-services >/dev/null 2>&1""",
    c="""\
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
systemctl is-enabled nftables.service 2>/dev/null | grep -q enabled && exit 0
dnf install -y iptables iptables-services""")
S["JR2.C.3.4.3.1.2"] = dict(
    ref=None, prose="Verify nftables is not run alongside iptables (masked when "
    "iptables is the active choice; N/A under firewalld or nftables).",
    v=f"""\
{_FW_ALT_NA}
systemctl is-enabled nftables.service 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active nftables.service 2>/dev/null | grep -q '^active' && exit 1
exit 0""",
    c="""\
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
systemctl stop nftables.service 2>/dev/null || true
systemctl mask nftables.service 2>/dev/null || true
exit 0""")
# 3.4.3.2.x / 3.4.3.3.x keep their derived cells: iptables/ip6tables commands
# are family-agnostic and already guarded. (No entries here on purpose.)

# ---- 4.1 cron --------------------------------------------------------------
S["JR2.C.4.1.1"] = dict(
    ref="2.4.1.1", prose="Verify the cron daemon is enabled and active (the EL "
    "unit is crond, not Debian's cron).",
    v="""\
rpm -q cronie >/dev/null 2>&1 || exit 101
systemctl is-enabled crond.service 2>/dev/null | grep -q enabled || exit 1
systemctl is-active crond.service 2>/dev/null | grep -q '^active' || exit 1
exit 0""",
    c="""\
rpm -q cronie >/dev/null 2>&1 || dnf install -y cronie
systemctl unmask crond.service 2>/dev/null || true
systemctl enable --now crond.service""")
for cid, ref, path in [
    ("JR2.C.4.1.2", "2.4.1.2", "/etc/crontab"),
    ("JR2.C.4.1.3", "2.4.1.3", "/etc/cron.hourly"),
    ("JR2.C.4.1.4", "2.4.1.4", "/etc/cron.daily"),
    ("JR2.C.4.1.5", "2.4.1.5", "/etc/cron.weekly"),
    ("JR2.C.4.1.6", "2.4.1.6", "/etc/cron.monthly"),
    ("JR2.C.4.1.7", "2.4.1.8", "/etc/cron.d"),
]:
    S[cid] = dict(ref=ref, prose=f"Verify access to {path} is restricted to root "
                  "(700 or stricter; 600 for the file).",
                  v=v_perm(path, "700", missing_ok=False),
                  c=f"""\
[ -e {path} ] || exit 0
chown root:root {path}
if [ -d {path} ]; then chmod og-rwx {path}; else chmod og-rwx,u-x {path}; fi""")
S["JR2.C.4.1.8"] = dict(
    ref="2.4.1.9", prose="Verify cron is restricted to authorised users "
    "(cron.allow exists, root-only; cron.deny absent or root-only).",
    v="""\
rpm -q cronie >/dev/null 2>&1 || exit 101
[ -f /etc/cron.allow ] || exit 1
set -- $(stat -Lc '%a %U %G' /etc/cron.allow)
m=$1 o=$2 g=$3
[ "$o" = root ] && [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
if [ -f /etc/cron.deny ]; then
  set -- $(stat -Lc '%a %U %G' /etc/cron.deny)
  m=$1 o=$2 g=$3
  [ "$o" = root ] && [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
fi
exit 0""",
    c="""\
touch /etc/cron.allow
chown root:root /etc/cron.allow
chmod 640 /etc/cron.allow
if [ -f /etc/cron.deny ]; then chown root:root /etc/cron.deny; chmod 640 /etc/cron.deny; fi
exit 0""")
S["JR2.C.4.1.9"] = dict(
    ref="2.4.2.1", prose="Verify at is restricted to authorised users (N/A when "
    "at is not installed).",
    v="""\
rpm -q at >/dev/null 2>&1 || exit 101
[ -f /etc/at.allow ] || exit 1
set -- $(stat -Lc '%a %U %G' /etc/at.allow)
m=$1 o=$2 g=$3
[ "$o" = root ] && [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
if [ -f /etc/at.deny ]; then
  set -- $(stat -Lc '%a %U %G' /etc/at.deny)
  m=$1 o=$2 g=$3
  [ "$o" = root ] && [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
fi
exit 0""",
    c="""\
rpm -q at >/dev/null 2>&1 || exit 0
touch /etc/at.allow
chown root:root /etc/at.allow
chmod 640 /etc/at.allow
if [ -f /etc/at.deny ]; then chown root:root /etc/at.deny; chmod 640 /etc/at.deny; fi
exit 0""")

# ---- 4.2 SSH ---------------------------------------------------------------
S["JR2.C.4.2.1"] = dict(
    ref="5.1.2", prose="Verify access to /etc/ssh/sshd_config is restricted (600 root:root).",
    v=v_perm("/etc/ssh/sshd_config", "600", missing_ok=False),
    c=c_perm("/etc/ssh/sshd_config", "600"))
S["JR2.C.4.2.2"] = dict(
    ref="5.1.4", prose="Verify SSH private host keys are protected — on EL the "
    "shipped default is root:ssh_keys 640; root:root 600 is also compliant.",
    v="""\
found=0
for f in /etc/ssh/ssh_host_*_key; do
  [ -e "$f" ] || continue
  found=1
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ "$o" = root ] || exit 1
  if [ "$g" = "ssh_keys" ]; then
    [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
  else
    [ "$g" = root ] && [ $(( 8#$m & 8#0177 )) -eq 0 ] || exit 1
  fi
done
[ "$found" -eq 1 ] && exit 0 || exit 101""",
    c="""\
for f in /etc/ssh/ssh_host_*_key; do
  [ -e "$f" ] || continue
  if getent group ssh_keys >/dev/null 2>&1; then
    chown root:ssh_keys "$f"; chmod 640 "$f"
  else
    chown root:root "$f"; chmod 600 "$f"
  fi
done
exit 0""")
S["JR2.C.4.2.3"] = dict(
    ref="5.1.5", prose="Verify SSH public host keys are not writable by others (644 root:root).",
    v="""\
found=0
for f in /etc/ssh/ssh_host_*_key.pub; do
  [ -e "$f" ] || continue
  found=1
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ "$o" = root ] && [ "$g" = root ] || exit 1
  [ $(( 8#$m & 8#0133 )) -eq 0 ] || exit 1
done
[ "$found" -eq 1 ] && exit 0 || exit 101""",
    c="""\
for f in /etc/ssh/ssh_host_*_key.pub; do
  [ -e "$f" ] || continue
  chown root:root "$f"
  chmod 644 "$f"
done
exit 0""")
S["JR2.C.4.2.4"] = dict(
    ref="5.1.6", prose="Verify sshd access is limited (an AllowUsers/AllowGroups/"
    "DenyUsers/DenyGroups directive is set).\nWhich principals to allow is a "
    "site decision, so no unattended remediation is authored.",
    v=v_sshd("echo \"$T\" | grep -Eq '^(allowusers|allowgroups|denyusers|denygroups)\\s'"),
    c=None)
S["JR2.C.4.2.5"] = dict(
    ref="5.1.16", prose="Verify the sshd LogLevel is VERBOSE or INFO.",
    v=v_sshd("echo \"$T\" | grep -Eq '^loglevel (verbose|info)$'"),
    c=c_sshd("LogLevel", "VERBOSE"))
S["JR2.C.4.2.6"] = dict(
    ref="5.1.24", prose="Verify sshd UsePAM is enabled.",
    v=v_sshd("echo \"$T\" | grep -q '^usepam yes$'"),
    c=c_sshd("UsePAM", "yes"))
S["JR2.C.4.2.7"] = dict(
    ref="5.1.22", prose="Verify sshd PermitRootLogin is disabled.",
    v=v_sshd("echo \"$T\" | grep -q '^permitrootlogin no$'"),
    c=c_sshd("PermitRootLogin", "no"))
S["JR2.C.4.2.8"] = dict(
    ref="5.1.12", prose="Verify sshd HostbasedAuthentication is disabled.",
    v=v_sshd("echo \"$T\" | grep -q '^hostbasedauthentication no$'"),
    c=c_sshd("HostbasedAuthentication", "no"))
S["JR2.C.4.2.9"] = dict(
    ref="5.1.21", prose="Verify sshd PermitEmptyPasswords is disabled.",
    v=v_sshd("echo \"$T\" | grep -q '^permitemptypasswords no$'"),
    c=c_sshd("PermitEmptyPasswords", "no"))
S["JR2.C.4.2.10"] = dict(
    ref="5.1.23", prose="Verify sshd PermitUserEnvironment is disabled.",
    v=v_sshd("echo \"$T\" | grep -q '^permituserenvironment no$'"),
    c=c_sshd("PermitUserEnvironment", "no"))
S["JR2.C.4.2.11"] = dict(
    ref="5.1.13", prose="Verify sshd IgnoreRhosts is enabled.",
    v=v_sshd("echo \"$T\" | grep -q '^ignorerhosts yes$'"),
    c=c_sshd("IgnoreRhosts", "yes"))
S["JR2.C.4.2.12"] = dict(
    ref="5.1.8", prose="Verify no weak SSH ciphers are offered.",
    v=v_sshd("echo \"$T\" | grep '^ciphers ' | grep -Eq "
             "'(3des-cbc|aes128-cbc|aes192-cbc|aes256-cbc|rc4|blowfish-cbc|cast128-cbc)' "
             "&& exit 1\nexit 0"),
    c=c_sshd("Ciphers",
             "aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr"))
S["JR2.C.4.2.13"] = dict(
    ref="5.1.17", prose="Verify no weak SSH MAC algorithms are offered.",
    v=v_sshd("echo \"$T\" | grep '^macs ' | grep -Eq "
             "'(hmac-md5|hmac-ripemd160|hmac-sha1-96|umac-64)' && exit 1\nexit 0"),
    c=c_sshd("MACs",
             "hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com,hmac-sha2-512,hmac-sha2-256"))
S["JR2.C.4.2.14"] = dict(
    ref="5.1.14", prose="Verify no weak SSH key-exchange algorithms are offered.",
    v=v_sshd("echo \"$T\" | grep '^kexalgorithms ' | grep -Eq "
             "'(diffie-hellman-group1-sha1|diffie-hellman-group14-sha1|diffie-hellman-group-exchange-sha1)' "
             "&& exit 1\nexit 0"),
    c=c_sshd("KexAlgorithms",
             "curve25519-sha256,curve25519-sha256@libssh.org,ecdh-sha2-nistp256,"
             "ecdh-sha2-nistp384,ecdh-sha2-nistp521,diffie-hellman-group14-sha256,"
             "diffie-hellman-group16-sha512,diffie-hellman-group18-sha512"))
S["JR2.C.4.2.15"] = dict(
    ref="5.1.7", prose="Verify an sshd Banner is configured.",
    v=v_sshd("echo \"$T\" | grep -Eq '^banner /\\S+'"),
    c=c_sshd("Banner", "/etc/issue.net"))
S["JR2.C.4.2.16"] = dict(
    ref="5.1.18", prose="Verify sshd MaxAuthTries is 4 or less (agreed value).",
    v=v_sshd("v=$(echo \"$T\" | awk '$1==\"maxauthtries\"{print $2}')\n"
             "[ -n \"$v\" ] && [ \"$v\" -le 4 ]"),
    c=c_sshd("MaxAuthTries", "4"))
S["JR2.C.4.2.17"] = dict(
    ref="5.1.20", prose="Verify sshd MaxStartups is 10:30:60 or more restrictive.",
    v=v_sshd("v=$(echo \"$T\" | awk '$1==\"maxstartups\"{print $2}' | cut -d: -f1)\n"
             "[ -n \"$v\" ] && [ \"$v\" -le 10 ]"),
    c=c_sshd("MaxStartups", "10:30:60"))
S["JR2.C.4.2.18"] = dict(
    ref="5.1.15", prose="Verify sshd LoginGraceTime is between 1 and 60 seconds (agreed value).",
    v=v_sshd("v=$(echo \"$T\" | awk '$1==\"logingracetime\"{print $2}')\n"
             "[ -n \"$v\" ] && [ \"$v\" -ge 1 ] && [ \"$v\" -le 60 ]"),
    c=c_sshd("LoginGraceTime", "60"))
S["JR2.C.4.2.19"] = dict(
    ref="5.1.19", prose="Verify sshd MaxSessions is 10 or less (agreed value).",
    v=v_sshd("v=$(echo \"$T\" | awk '$1==\"maxsessions\"{print $2}')\n"
             "[ -n \"$v\" ] && [ \"$v\" -le 10 ]"),
    c=c_sshd("MaxSessions", "10"))
S["JR2.C.4.2.20"] = dict(
    ref="5.1.9", prose="Verify the SSH idle-timeout values are non-zero "
    "(ClientAliveInterval and ClientAliveCountMax — agreed value).",
    v=v_sshd("i=$(echo \"$T\" | awk '$1==\"clientaliveinterval\"{print $2}')\n"
             "c=$(echo \"$T\" | awk '$1==\"clientalivecountmax\"{print $2}')\n"
             "[ -n \"$i\" ] && [ -n \"$c\" ] && [ \"$i\" -ge 1 ] && [ \"$c\" -ge 1 ]"),
    c="""\
cfg=/etc/ssh/sshd_config
if grep -Eiq '^\\s*Include\\s+/etc/ssh/sshd_config.d' "$cfg" && [ -d /etc/ssh/sshd_config.d ]; then
  printf 'ClientAliveInterval 300\\nClientAliveCountMax 3\\n' > /etc/ssh/sshd_config.d/60-criclo-clientalive.conf
else
  sed -ri 's/^\\s*#?\\s*ClientAliveInterval\\b.*/ClientAliveInterval 300/I' "$cfg"
  grep -Eiq '^\\s*ClientAliveInterval\\b' "$cfg" || printf 'ClientAliveInterval 300\\n' >> "$cfg"
  sed -ri 's/^\\s*#?\\s*ClientAliveCountMax\\b.*/ClientAliveCountMax 3/I' "$cfg"
  grep -Eiq '^\\s*ClientAliveCountMax\\b' "$cfg" || printf 'ClientAliveCountMax 3\\n' >> "$cfg"
fi
sshd -t || exit 1
systemctl reload sshd 2>/dev/null || true
exit 0""")

# ---- 4.3 sudo --------------------------------------------------------------
S["JR2.C.4.3.1"] = dict(
    ref="5.2.1", prose="Verify sudo is installed.",
    v=v_pkg_present(["sudo"]), c=c_pkg_present(["sudo"]))
S["JR2.C.4.3.2"] = dict(
    ref="5.2.2", prose="Verify sudo commands run in a pseudo-terminal (Defaults use_pty).",
    v="""\
grep -Ersq '^\\s*Defaults\\s+([^#]*,\\s*)?use_pty\\b' /etc/sudoers /etc/sudoers.d 2>/dev/null""",
    c="""\
printf 'Defaults use_pty\\n' > /etc/sudoers.d/60-criclo-use-pty
chmod 440 /etc/sudoers.d/60-criclo-use-pty
visudo -cf /etc/sudoers >/dev/null || { rm -f /etc/sudoers.d/60-criclo-use-pty; exit 1; }
exit 0""")
S["JR2.C.4.3.3"] = dict(
    ref="5.2.3", prose="Verify a sudo log file is configured.",
    v="""\
grep -Ersq '^\\s*Defaults\\s+([^#]*,\\s*)?logfile\\s*=' /etc/sudoers /etc/sudoers.d 2>/dev/null""",
    c="""\
printf 'Defaults logfile="/var/log/sudo.log"\\n' > /etc/sudoers.d/60-criclo-logfile
chmod 440 /etc/sudoers.d/60-criclo-logfile
visudo -cf /etc/sudoers >/dev/null || { rm -f /etc/sudoers.d/60-criclo-logfile; exit 1; }
exit 0""")
S["JR2.C.4.3.4"] = dict(
    ref="5.2.5", prose="Verify re-authentication for privilege escalation is not "
    "disabled (no !authenticate).\nRemoving a hand-written sudoers entry needs "
    "review, so no unattended remediation is authored.",
    v="""\
grep -Ersq '^\\s*[^#]*\\!authenticate' /etc/sudoers /etc/sudoers.d 2>/dev/null && exit 1
exit 0""",
    c=None)
S["JR2.C.4.3.5"] = dict(
    ref="5.2.6", prose="Verify the sudo authentication timeout is 15 minutes or "
    "less (agreed value; the compiled default of 5 also complies).",
    v="""\
vals=$(grep -Ersho 'timestamp_timeout\\s*=\\s*-?[0-9]+' /etc/sudoers /etc/sudoers.d 2>/dev/null | grep -Eo '[-0-9]+')
[ -z "$vals" ] && exit 0
for v in $vals; do
  [ "$v" -ge 0 ] && [ "$v" -le 15 ] || exit 1
done
exit 0""",
    c="""\
grep -Ersl 'timestamp_timeout' /etc/sudoers /etc/sudoers.d 2>/dev/null | while read -r f; do
  sed -ri 's/timestamp_timeout\\s*=\\s*-?[0-9]+/timestamp_timeout=15/g' "$f"
done
visudo -cf /etc/sudoers >/dev/null || exit 1
exit 0""")
S["JR2.C.4.3.6"] = dict(
    ref="5.2.7", prose="Verify access to the su command is restricted via pam_wheel "
    "with an authorised (possibly empty) group.",
    v="""\
grep -Eq '^\\s*auth\\s+(required|requisite)\\s+pam_wheel\\.so\\s+([^#]*\\s)?use_uid' /etc/pam.d/su""",
    c="""\
getent group sugroup >/dev/null 2>&1 || groupadd sugroup
if grep -Eq '^\\s*#\\s*auth\\s+required\\s+pam_wheel\\.so' /etc/pam.d/su; then
  sed -ri 's/^\\s*#\\s*(auth\\s+required\\s+pam_wheel\\.so).*/\\1 use_uid group=sugroup/' /etc/pam.d/su
elif ! grep -Eq '^\\s*auth\\s+(required|requisite)\\s+pam_wheel\\.so' /etc/pam.d/su; then
  sed -ri '0,/^auth/s//auth            required        pam_wheel.so use_uid group=sugroup\\n&/' /etc/pam.d/su
fi
exit 0""")

# ---- 4.4 PAM (authselect / faillock / pwquality) ---------------------------
S["JR2.C.4.4.1"] = dict(
    ref="5.3.3.2.2", prose="Verify password creation requirements (pwquality: "
    "minlen ≥ 14 and 4 character classes) — the EL stack reads "
    "/etc/security/pwquality.conf(.d).",
    v="""\
rpm -q libpwquality >/dev/null 2>&1 || exit 1
conf() { awk -F= -v k="$1" '$1 ~ "^\\\\s*"k"\\\\s*$" {gsub(/ /,"",$2); v=$2} END {print v}' \\
  /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null; }
ml=$(conf minlen); [ -n "$ml" ] && [ "$ml" -ge 14 ] || exit 1
mc=$(conf minclass)
if [ -n "$mc" ]; then [ "$mc" -ge 4 ] || exit 1
else
  for k in dcredit ucredit lcredit ocredit; do
    cv=$(conf $k); [ -n "$cv" ] && [ "$cv" -le -1 ] || exit 1
  done
fi
grep -Eq 'pam_pwquality\\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth || exit 1
exit 0""",
    c="""\
mkdir -p /etc/security/pwquality.conf.d
printf 'minlen = 14\\nminclass = 4\\n' > /etc/security/pwquality.conf.d/60-criclo-pwquality.conf
exit 0""")
S["JR2.C.4.4.2"] = dict(
    ref="5.3.3.1.1", prose="Verify account lockout on failed attempts "
    "(faillock: deny ≤ 5 and unlock_time 0 or ≥ 900).",
    v="""\
d=$(awk -F= '/^\\s*deny\\s*=/ {gsub(/ /,"",$2); print $2}' /etc/security/faillock.conf 2>/dev/null | tail -n1)
u=$(awk -F= '/^\\s*unlock_time\\s*=/ {gsub(/ /,"",$2); print $2}' /etc/security/faillock.conf 2>/dev/null | tail -n1)
[ -n "$d" ] && [ "$d" -ge 1 ] && [ "$d" -le 5 ] || exit 1
[ -n "$u" ] && { [ "$u" -eq 0 ] || [ "$u" -ge 900 ]; } || exit 1
grep -Eq 'pam_faillock\\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth || exit 1
exit 0""",
    c="""\
grep -Eq '^\\s*deny\\s*=' /etc/security/faillock.conf 2>/dev/null \\
  && sed -ri 's/^\\s*(#\\s*)?deny\\s*=.*/deny = 5/' /etc/security/faillock.conf \\
  || printf 'deny = 5\\n' >> /etc/security/faillock.conf
grep -Eq '^\\s*unlock_time\\s*=' /etc/security/faillock.conf 2>/dev/null \\
  && sed -ri 's/^\\s*(#\\s*)?unlock_time\\s*=.*/unlock_time = 900/' /etc/security/faillock.conf \\
  || printf 'unlock_time = 900\\n' >> /etc/security/faillock.conf
if command -v authselect >/dev/null 2>&1 && authselect current >/dev/null 2>&1; then
  authselect enable-feature with-faillock 2>/dev/null || true
  authselect apply-changes 2>/dev/null || true
fi
exit 0""")
S["JR2.C.4.4.3"] = dict(
    ref="5.3.3.3.1", prose="Verify password reuse is limited to the last 5 "
    "passwords (agreed value; pam_pwhistory remember ≥ 5).",
    v="""\
r=$(awk -F= '/^\\s*remember\\s*=/ {gsub(/ /,"",$2); print $2}' /etc/security/pwhistory.conf 2>/dev/null | tail -n1)
[ -z "$r" ] && r=$(grep -Eo 'pam_pwhistory\\.so[^#]*remember=[0-9]+' /etc/pam.d/system-auth 2>/dev/null | grep -Eo '[0-9]+' | tail -n1)
[ -n "$r" ] && [ "$r" -ge 5 ]""",
    c="""\
if [ -f /etc/security/pwhistory.conf ]; then
  grep -Eq '^\\s*remember\\s*=' /etc/security/pwhistory.conf \\
    && sed -ri 's/^\\s*(#\\s*)?remember\\s*=.*/remember = 5/' /etc/security/pwhistory.conf \\
    || printf 'remember = 5\\n' >> /etc/security/pwhistory.conf
else
  printf 'remember = 5\\n' > /etc/security/pwhistory.conf
fi
if command -v authselect >/dev/null 2>&1 && authselect current >/dev/null 2>&1; then
  authselect enable-feature with-pwhistory 2>/dev/null || true
  authselect apply-changes 2>/dev/null || true
fi
exit 0""")
S["JR2.C.4.4.4"] = dict(
    ref="5.4.1.4", prose="Verify the password hashing algorithm is SHA-512 or "
    "yescrypt (login.defs and pam_unix).",
    v="""\
grep -Eiq '^\\s*ENCRYPT_METHOD\\s+(SHA512|YESCRYPT)\\b' /etc/login.defs || exit 1
grep -E 'pam_unix\\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth 2>/dev/null | grep -Eq '\\b(md5|des|bigcrypt|blowfish)\\b' && exit 1
exit 0""",
    c="""\
sed -ri 's/^\\s*#?\\s*ENCRYPT_METHOD\\b.*/ENCRYPT_METHOD SHA512/' /etc/login.defs
grep -Eq '^\\s*ENCRYPT_METHOD\\b' /etc/login.defs || printf 'ENCRYPT_METHOD SHA512\\n' >> /etc/login.defs
exit 0""")
S["JR2.C.4.4.5"] = dict(
    ref="5.4.2.7", prose="Verify system accounts have no valid login shell (or are locked).",
    v="""\
umin=$(awk '/^\\s*UID_MIN/{print $2}' /etc/login.defs)
[ -n "$umin" ] || umin=1000
bad=$(awk -F: -v m="$umin" '($1!~/^(root|halt|sync|shutdown|nfsnobody)$/ && ($3<m || $3==65534) && $7!~/(nologin|\\/bin\\/false)$/) {print $1}' /etc/passwd)
[ -z "$bad" ]""",
    c="""\
umin=$(awk '/^\\s*UID_MIN/{print $2}' /etc/login.defs)
[ -n "$umin" ] || umin=1000
awk -F: -v m="$umin" '($1!~/^(root|halt|sync|shutdown|nfsnobody)$/ && ($3<m || $3==65534) && $7!~/(nologin|\\/bin\\/false)$/) {print $1}' /etc/passwd | \\
while read -r u; do
  usermod -s /sbin/nologin "$u"
  usermod -L "$u"
done
exit 0""")

# ---- 4.5 login policy ------------------------------------------------------
S["JR2.C.4.5.1"] = dict(
    ref="5.4.2.2", prose="Verify the root account's primary group is GID 0.",
    v='[ "$(id -g root)" = "0" ]',
    c="usermod -g 0 root")
S["JR2.C.4.5.2"] = dict(
    ref="5.4.3.3", prose="Verify the default user umask is 027 or more restrictive.",
    v="""\
u=$(awk '/^\\s*UMASK\\s/ {print $2}' /etc/login.defs | tail -n1)
case "$u" in 027|077) : ;; *) exit 1 ;; esac
grep -Ersq '^\\s*umask\\s+0?(0[0-2][0-7]|[0-2][0-7])\\b' /etc/profile /etc/profile.d /etc/bashrc 2>/dev/null && exit 1
exit 0""",
    c="""\
sed -ri 's/^\\s*UMASK\\s+.*/UMASK 027/' /etc/login.defs
grep -Eq '^\\s*UMASK\\b' /etc/login.defs || printf 'UMASK 027\\n' >> /etc/login.defs
printf 'umask 027\\n' > /etc/profile.d/60-criclo-umask.sh
exit 0""")
S["JR2.C.4.5.3"] = dict(
    ref="5.4.3.2", prose="Verify the default shell timeout is between 1 and 900 "
    "seconds (agreed value).",
    v="""\
t=$(grep -Ersho 'TMOUT=[0-9]+' /etc/profile /etc/profile.d /etc/bashrc 2>/dev/null | grep -Eo '[0-9]+' | tail -n1)
[ -n "$t" ] && [ "$t" -ge 1 ] && [ "$t" -le 900 ]""",
    c="""\
printf 'typeset -xr TMOUT=900\\n' > /etc/profile.d/60-criclo-tmout.sh
exit 0""")
S["JR2.C.4.5.4"] = dict(
    ref="5.3.3.2.4", prose="Verify no more than 3 identical consecutive characters "
    "are allowed in a password (pwquality maxrepeat 1–3, agreed value).",
    v=v_pwquality("maxrepeat", '[ "$v" -ge 1 ] && [ "$v" -le 3 ]'),
    c=c_pwquality("maxrepeat", "3"))
S["JR2.C.4.5.1.1"] = dict(
    ref="5.4.1.2", prose="Verify PASS_MIN_DAYS is 1 or more (agreed value), for "
    "the policy and existing users.",
    v=v_logindefs("PASS_MIN_DAYS", '[ "$v" -ge 1 ] || exit 1\n'
                  "bad=$(awk -F: '($2!~/^[!*]/ && $4<1) {print $1}' /etc/shadow)\n"
                  '[ -z "$bad" ]'),
    c=c_logindefs("PASS_MIN_DAYS", "1", "--mindays"))
S["JR2.C.4.5.1.2"] = dict(
    ref="5.4.1.1", prose="Verify password expiration is 365 days or less, for the "
    "policy and existing users.",
    v=v_logindefs("PASS_MAX_DAYS", '[ "$v" -ge 1 ] && [ "$v" -le 365 ] || exit 1\n'
                  "bad=$(awk -F: '($2!~/^[!*]/ && ($5>365 || $5 == \"\" || $5 == -1)) {print $1}' /etc/shadow)\n"
                  '[ -z "$bad" ]'),
    c=c_logindefs("PASS_MAX_DAYS", "365", "--maxdays"))
S["JR2.C.4.5.1.3"] = dict(
    ref="5.4.1.3", prose="Verify the password expiration warning is 7 days or more "
    "(agreed value).",
    v=v_logindefs("PASS_WARN_AGE", '[ "$v" -ge 7 ] || exit 1\n'
                  "bad=$(awk -F: '($2!~/^[!*]/ && $6<7) {print $1}' /etc/shadow)\n"
                  '[ -z "$bad" ]'),
    c=c_logindefs("PASS_WARN_AGE", "7", "--warndays"))
S["JR2.C.4.5.1.4"] = dict(
    ref="5.4.1.5", prose="Verify the inactive password lock is 30 days or less.",
    v="""\
d=$(useradd -D | awk -F= '/INACTIVE/{print $2}')
[ -n "$d" ] && [ "$d" -ge 0 ] && [ "$d" -le 30 ] || exit 1
bad=$(awk -F: '($2!~/^[!*]/ && ($7 == "" || $7 > 30 || $7 < 0)) {print $1}' /etc/shadow)
[ -z "$bad" ]""",
    c="""\
useradd -D -f 30
awk -F: '($2!~/^[!*]/) {print $1}' /etc/shadow | while read -r u; do
  chage --inactive 30 "$u"
done
exit 0""")
S["JR2.C.4.5.1.5"] = dict(
    ref="5.4.1.6", prose="Verify every user's last password change date is in the "
    "past.\nA future-dated stamp needs operator investigation, so no unattended "
    "remediation is authored.",
    v="""\
now=$(( $(date +%s) / 86400 ))
bad=$(awk -F: -v now="$now" '($3 != "" && $3 > now) {print $1}' /etc/shadow)
[ -z "$bad" ]""",
    c=None)
S["JR2.C.4.5.1.6"] = dict(
    ref="5.3.3.2.1", prose="Verify at least 2 characters must change in a new "
    "password (pwquality difok ≥ 2, agreed value).",
    v=v_pwquality("difok", '[ "$v" -ge 2 ]'),
    c=c_pwquality("difok", "2"))
S["JR2.C.4.5.1.7"] = dict(
    ref="5.3.3.2.6", prose="Verify the password dictionary check is enabled "
    "(pwquality dictcheck not disabled).",
    v="""\
rpm -q libpwquality >/dev/null 2>&1 || exit 1
v=$(awk -F= '/^\\s*dictcheck\\s*=/ {gsub(/ /,"",$2); print $2}' \\
    /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -n1)
[ -z "$v" ] || [ "$v" != "0" ]""",
    c=c_pwquality("dictcheck", "1"))

# ---- 5.1 logging -----------------------------------------------------------
S["JR2.C.5.1.1"] = dict(
    ref="6.2.3.1", prose="Verify no log file under /var/log is world-writable and "
    "the sensitive system logs are not world-readable.",
    v="""\
find -L /var/log -type f -perm /o+w ! -path '*/journal/*' 2>/dev/null | grep -q . && exit 1
for f in /var/log/secure /var/log/messages /var/log/maillog /var/log/cron; do
  [ -e "$f" ] || continue
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
done
exit 0""",
    c="""\
find -L /var/log -type f -perm /o+w ! -path '*/journal/*' -exec chmod o-w {} + 2>/dev/null
for f in /var/log/secure /var/log/messages /var/log/maillog /var/log/cron; do
  [ -e "$f" ] && chmod u-x,g-wx,o-rwx "$f"
done
exit 0""")
S["JR2.C.5.1.1.1"] = dict(
    ref="6.2.1.1.1", prose="Verify the systemd-journald service is active.",
    v="""\
systemctl is-active systemd-journald.service 2>/dev/null | grep -q '^active'""",
    c="""\
systemctl unmask systemd-journald.service 2>/dev/null || true
systemctl start systemd-journald.service""")
S["JR2.C.5.1.1.2"] = dict(
    ref="6.2.1.1.6", prose="Verify journald compresses large log files.",
    v="""\
grep -Ersq '^\\s*Compress=yes' /etc/systemd/journald.conf /etc/systemd/journald.conf.d 2>/dev/null""",
    c="""\
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\\nCompress=yes\\n' > /etc/systemd/journald.conf.d/60-criclo-compress.conf
systemctl restart systemd-journald.service 2>/dev/null || true
exit 0""")
S["JR2.C.5.1.1.3"] = dict(
    ref="6.2.1.1.5", prose="Verify journald writes logs to persistent storage.",
    v="""\
grep -Ersq '^\\s*Storage=persistent' /etc/systemd/journald.conf /etc/systemd/journald.conf.d 2>/dev/null""",
    c="""\
mkdir -p /etc/systemd/journald.conf.d /var/log/journal
printf '[Journal]\\nStorage=persistent\\n' > /etc/systemd/journald.conf.d/60-criclo-storage.conf
systemctl restart systemd-journald.service 2>/dev/null || true
exit 0""")
S["JR2.C.5.1.1.1.1"] = dict(
    ref="6.2.1.2.1", prose="Verify systemd-journal-remote is installed (for "
    "forwarding logs to a remote collector).",
    v=v_pkg_present(["systemd-journal-remote"]),
    c=c_pkg_present(["systemd-journal-remote"]))
S["JR2.C.5.1.1.1.2"] = dict(
    ref="6.2.1.2.4", prose="Verify journald does not accept logs from remote clients.",
    v=v_svc_inert(["systemd-journal-remote.socket", "systemd-journal-remote.service"]),
    c=c_svc_inert(["systemd-journal-remote.socket", "systemd-journal-remote.service"]))
S["JR2.C.5.1.2.1"] = dict(
    ref="6.2.2.1", prose="Verify rsyslog is installed.",
    v=v_pkg_present(["rsyslog"]), c=c_pkg_present(["rsyslog"]))
S["JR2.C.5.1.2.2"] = dict(
    ref="6.2.2.2", prose="Verify the rsyslog service is enabled and active "
    "(N/A when rsyslog is not installed).",
    v="""\
rpm -q rsyslog >/dev/null 2>&1 || exit 101
systemctl is-enabled rsyslog.service 2>/dev/null | grep -q enabled || exit 1
systemctl is-active rsyslog.service 2>/dev/null | grep -q '^active' || exit 1
exit 0""",
    c="""\
rpm -q rsyslog >/dev/null 2>&1 || exit 0
systemctl unmask rsyslog.service 2>/dev/null || true
systemctl enable --now rsyslog.service""")
S["JR2.C.5.1.2.3"] = dict(
    ref="6.2.2.4", prose="Verify rsyslog creates log files 0640 or stricter "
    "(N/A when rsyslog is not installed).",
    v="""\
rpm -q rsyslog >/dev/null 2>&1 || exit 101
m=$(grep -Ersh '^\\$FileCreateMode\\s+[0-7]+' /etc/rsyslog.conf /etc/rsyslog.d 2>/dev/null | awk '{print $2}' | tail -n1)
[ -n "$m" ] || exit 1
[ $(( 8#$m & 8#0137 )) -eq 0 ]""",
    c="""\
rpm -q rsyslog >/dev/null 2>&1 || exit 0
printf '$FileCreateMode 0640\\n' > /etc/rsyslog.d/60-criclo-filemode.conf
systemctl try-restart rsyslog.service 2>/dev/null || true
exit 0""")
S["JR2.C.5.1.2.4"] = dict(
    ref="6.2.2.7", prose="Verify rsyslog does not listen for remote logs "
    "(no active imtcp/imudp module — N/A when rsyslog is not installed).",
    v="""\
rpm -q rsyslog >/dev/null 2>&1 || exit 101
grep -Ersq '^\\s*(module\\(load="imtcp"\\)|module\\(load="imudp"\\)|\\$ModLoad\\s+(imtcp|imudp))' /etc/rsyslog.conf /etc/rsyslog.d 2>/dev/null && exit 1
grep -Ersq '^\\s*(input\\(type="imtcp"|input\\(type="imudp"|\\$(InputTCPServerRun|UDPServerRun))' /etc/rsyslog.conf /etc/rsyslog.d 2>/dev/null && exit 1
exit 0""",
    c="""\
rpm -q rsyslog >/dev/null 2>&1 || exit 0
for f in /etc/rsyslog.conf /etc/rsyslog.d/*.conf; do
  [ -f "$f" ] || continue
  sed -ri 's/^(\\s*module\\(load="im(tcp|udp)"\\).*)/#\\1/' "$f"
  sed -ri 's/^(\\s*input\\(type="im(tcp|udp)".*)/#\\1/' "$f"
  sed -ri 's/^(\\s*\\$ModLoad\\s+im(tcp|udp).*)/#\\1/' "$f"
  sed -ri 's/^(\\s*\\$(InputTCPServerRun|UDPServerRun).*)/#\\1/' "$f"
done
systemctl try-restart rsyslog.service 2>/dev/null || true
exit 0""")
S["JR2.C.5.1.3.1"] = dict(
    ref="6.1.3", prose="Verify AIDE protects the integrity of the audit tools "
    "with cryptographic hashes (N/A when AIDE is not installed).",
    v="""\
rpm -q aide >/dev/null 2>&1 || exit 101
for t in /usr/sbin/auditctl /usr/sbin/auditd /usr/sbin/ausearch /usr/sbin/aureport /usr/sbin/autrace /usr/sbin/augenrules; do
  grep -Eq "^\\s*${t}\\s+.*(sha512|sha256)" /etc/aide.conf /etc/aide.conf.d/*.conf 2>/dev/null || exit 1
done
exit 0""",
    c="""\
rpm -q aide >/dev/null 2>&1 || exit 0
for t in /usr/sbin/auditctl /usr/sbin/auditd /usr/sbin/ausearch /usr/sbin/aureport /usr/sbin/autrace /usr/sbin/augenrules; do
  grep -Eq "^\\s*${t}\\s" /etc/aide.conf 2>/dev/null || \\
    printf '%s p+i+n+u+g+s+b+acl+xattrs+sha512\\n' "$t" >> /etc/aide.conf
done
exit 0""")

# ---- 6.1 file permissions --------------------------------------------------
for cid, ref, path, mode in [
    ("JR2.C.6.1.1", "7.1.1", "/etc/passwd", "644"),
    ("JR2.C.6.1.2", "7.1.2", "/etc/passwd-", "644"),
    ("JR2.C.6.1.3", "7.1.3", "/etc/group", "644"),
    ("JR2.C.6.1.4", "7.1.4", "/etc/group-", "644"),
    ("JR2.C.6.1.9", "7.1.9", "/etc/shells", "644"),
]:
    S[cid] = dict(ref=ref, prose=f"Verify access to {path} is configured "
                  f"({mode} root:root).",
                  v=v_perm(path, mode, missing_ok=(path.endswith("-"))),
                  c=c_perm(path, mode))
for cid, ref, path in [
    ("JR2.C.6.1.5", "7.1.5", "/etc/shadow"),
    ("JR2.C.6.1.6", "7.1.6", "/etc/shadow-"),
    ("JR2.C.6.1.7", "7.1.7", "/etc/gshadow"),
    ("JR2.C.6.1.8", "7.1.8", "/etc/gshadow-"),
]:
    S[cid] = dict(ref=ref, prose=f"Verify access to {path} is restricted to root "
                  "(0000 root:root — the EL default; Debian's root:shadow 640 "
                  "does not apply here).",
                  v=v_perm(path, "0", missing_ok=path.endswith("-")),
                  c=c_perm(path, "0"))
S["JR2.C.6.1.10"] = dict(
    ref="7.1.10", prose="Verify access to /etc/security/opasswd is restricted "
    "(600 root:root — the EL path differs from Debian's /etc/opasswd).",
    v="""\
for f in /etc/security/opasswd /etc/security/opasswd.old; do
  [ -e "$f" ] || continue
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ "$o" = root ] && [ "$g" = root ] || exit 1
  [ $(( 8#$m & 8#0177 )) -eq 0 ] || exit 1
done
exit 0""",
    c="""\
for f in /etc/security/opasswd /etc/security/opasswd.old; do
  [ -e "$f" ] || continue
  chown root:root "$f"
  chmod 600 "$f"
done
exit 0""")
S["JR2.C.6.1.11"] = dict(
    ref="7.1.11", prose="Verify no world-writable files exist and world-writable "
    "directories carry the sticky bit.",
    v="""\
find / -xdev \\( -path /proc -o -path /sys -o -path /run -o -path /tmp -o -path /var/tmp -o -path /dev/shm \\) -prune \\
  -o -type f -perm -0002 -print 2>/dev/null | grep -q . && exit 1
find / -xdev \\( -path /proc -o -path /sys -o -path /run \\) -prune \\
  -o -type d -perm -0002 ! -perm -1000 -print 2>/dev/null | grep -q . && exit 1
exit 0""",
    c="""\
find / -xdev \\( -path /proc -o -path /sys -o -path /run -o -path /tmp -o -path /var/tmp -o -path /dev/shm \\) -prune \\
  -o -type f -perm -0002 -exec chmod o-w {} + 2>/dev/null
find / -xdev \\( -path /proc -o -path /sys -o -path /run \\) -prune \\
  -o -type d -perm -0002 ! -perm -1000 -exec chmod a+t {} + 2>/dev/null
exit 0""")
S["JR2.C.6.1.12"] = dict(
    ref="7.1.12", prose="Verify no unowned or ungrouped files exist.\nRe-owning "
    "such files needs operator investigation, so no unattended remediation is "
    "authored.",
    v="""\
find / -xdev \\( -path /proc -o -path /sys -o -path /run \\) -prune \\
  -o \\( -nouser -o -nogroup \\) -print 2>/dev/null | grep -q . && exit 1
exit 0""",
    c=None)

# ---- 6.2 accounts ----------------------------------------------------------
S["JR2.C.6.2.1"] = dict(
    ref="7.2.1", prose="Verify every /etc/passwd account uses a shadowed password.",
    v="""\
awk -F: '($2 != "x") {print $1}' /etc/passwd | grep -q . && exit 1
exit 0""",
    c="""\
pwconv
exit 0""")
S["JR2.C.6.2.2"] = dict(
    ref="7.2.2", prose="Verify no /etc/shadow password field is empty (empty "
    "fields are locked, not given a password).",
    v="""\
awk -F: '($2 == "") {print $1}' /etc/shadow | grep -q . && exit 1
exit 0""",
    c="""\
awk -F: '($2 == "") {print $1}' /etc/shadow | while read -r u; do
  passwd -l "$u"
done
exit 0""")
S["JR2.C.6.2.3"] = dict(
    ref="7.2.3", prose="Verify every group referenced in /etc/passwd exists in "
    "/etc/group.\nCreating missing groups needs operator review, so no "
    "unattended remediation is authored.",
    v="""\
for g in $(cut -d: -f4 /etc/passwd | sort -u); do
  getent group "$g" >/dev/null || exit 1
done
exit 0""",
    c=None)
S["JR2.C.6.2.4"] = dict(
    ref=None, prose="The Red Hat family has no `shadow` group convention "
    "(Debian-specific) — N/A unless such a group exists, in which case it must "
    "be empty.",
    v="""\
getent group shadow >/dev/null 2>&1 || exit 101
[ -z "$(getent group shadow | cut -d: -f4)" ] || exit 1
awk -F: -v g="$(getent group shadow | cut -d: -f3)" '($4 == g) {print $1}' /etc/passwd | grep -q . && exit 1
exit 0""",
    c=None)
for cid, ref, field_, what in [
    ("JR2.C.6.2.5", "7.2.4", "3", "UIDs"),
    ("JR2.C.6.2.6", "7.2.5", "4", "GIDs"),
]:
    S[cid] = dict(ref=ref, prose=f"Verify no duplicate {what} exist.\nMerging "
                  "duplicate accounts needs operator review, so no unattended "
                  "remediation is authored.",
                  v=f"""\
cut -d: -f{field_} /etc/{'passwd' if field_ == '3' else 'group'} | sort | uniq -d | grep -q . && exit 1
exit 0""",
                  c=None)
S["JR2.C.6.2.7"] = dict(
    ref="7.2.6", prose="Verify no duplicate user names exist.",
    v="""\
cut -d: -f1 /etc/passwd | sort | uniq -d | grep -q . && exit 1
exit 0""",
    c=None)
S["JR2.C.6.2.8"] = dict(
    ref="7.2.7", prose="Verify no duplicate group names exist.",
    v="""\
cut -d: -f1 /etc/group | sort | uniq -d | grep -q . && exit 1
exit 0""",
    c=None)
S["JR2.C.6.2.9"] = dict(
    ref="5.4.2.5", prose="Verify root's PATH contains no empty segment, no '.', "
    "and only root-owned, non-world/group-writable directories.",
    v="""\
p=$(su - root -c 'echo "$PATH"' 2>/dev/null | tail -n1)
[ -n "$p" ] || p="$PATH"
case ":$p:" in *::*|*:.:*) exit 1 ;; esac
case "$p" in *:) exit 1 ;; esac
IFS=:
for d in $p; do
  [ -d "$d" ] || continue
  set -- $(stat -Lc '%a %U %G' "$d")
m=$1 o=$2 g=$3
  [ "$o" = root ] || exit 1
  [ $(( 8#$m & 8#0022 )) -eq 0 ] || exit 1
done
exit 0""",
    c=None)
S["JR2.C.6.2.10"] = dict(
    ref="5.4.2.1", prose="Verify root is the only UID 0 account.\nRemoving another "
    "UID-0 account needs operator review, so no unattended remediation is authored.",
    v="""\
[ "$(awk -F: '($3 == 0) {print $1}' /etc/passwd)" = "root" ]""",
    c=None)
S["JR2.C.6.2.11"] = dict(
    ref="7.2.8", prose="Verify local interactive users own their home directories, "
    "which are not group/world-writable.",
    v="""\
umin=$(awk '/^\\s*UID_MIN/{print $2}' /etc/login.defs); [ -n "$umin" ] || umin=1000
awk -F: -v m="$umin" '($3>=m && $7!~/(nologin|\\/bin\\/false)$/) {print $1":"$6}' /etc/passwd | \\
while IFS=: read -r u h; do
  [ -d "$h" ] || exit 1
  set -- $(stat -Lc '%a %U %G' "$h")
mm=$1 o=$2 g=$3
  [ "$o" = "$u" ] || exit 1
  [ $(( 8#$mm & 8#0022 )) -eq 0 ] || exit 1
done""",
    c="""\
umin=$(awk '/^\\s*UID_MIN/{print $2}' /etc/login.defs); [ -n "$umin" ] || umin=1000
awk -F: -v m="$umin" '($3>=m && $7!~/(nologin|\\/bin\\/false)$/) {print $1":"$6}' /etc/passwd | \\
while IFS=: read -r u h; do
  [ -d "$h" ] || { mkdir -p "$h"; chown "$u" "$h"; }
  chown "$u" "$h"
  chmod g-w,o-rwx "$h"
done
exit 0""")
S["JR2.C.6.2.12"] = dict(
    ref="7.2.9", prose="Verify local interactive users' dot files are not "
    "group/world-writable and no .netrc/.rhosts/.forward files exist.",
    v="""\
umin=$(awk '/^\\s*UID_MIN/{print $2}' /etc/login.defs); [ -n "$umin" ] || umin=1000
awk -F: -v m="$umin" '($3>=m && $7!~/(nologin|\\/bin\\/false)$/) {print $6}' /etc/passwd | \\
while read -r h; do
  [ -d "$h" ] || continue
  for f in "$h"/.netrc "$h"/.rhosts "$h"/.forward; do
    [ -e "$f" ] && exit 1
  done
  find "$h" -maxdepth 1 -name '.*' -type f -perm /go+w 2>/dev/null | grep -q . && exit 1
done
exit 0""",
    c="""\
umin=$(awk '/^\\s*UID_MIN/{print $2}' /etc/login.defs); [ -n "$umin" ] || umin=1000
awk -F: -v m="$umin" '($3>=m && $7!~/(nologin|\\/bin\\/false)$/) {print $6}' /etc/passwd | \\
while read -r h; do
  [ -d "$h" ] || continue
  find "$h" -maxdepth 1 -name '.*' -type f -perm /go+w -exec chmod go-w {} + 2>/dev/null
done
exit 0""")


# ── CSV rewrite ──────────────────────────────────────────────────────────────

def norm_header(h: str) -> str:
    h = (h or "").strip().lower().replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", h)


def main() -> int:
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    hmap = {norm_header(k): k for k in fieldnames}
    col_vr = hmap["validate - red hat family"]
    col_cr = hmap["configure - red hat family"]
    col_ap = hmap["applies to"]
    col_id = hmap["control id"]
    col_ty = hmap["type"]

    written = debianized = untouched = 0
    seen: set[str] = set()
    for r in rows:
        if (r.get(col_ty) or "control").strip().lower() == "section":
            continue
        cid = (r.get(col_id) or "").strip()
        spec = S.get(cid)
        if spec is None:
            untouched += 1
            continue
        seen.add(cid)
        if spec.get("debian_only"):
            r[col_ap] = "debian"
            r[col_vr] = ""
            r[col_cr] = ""
            debianized += 1
            continue
        ref, note, prose = spec.get("ref"), spec.get("note"), spec.get("prose", "")
        r[col_vr] = cell(ref, prose, spec.get("v"), note)
        if spec.get("c"):
            r[col_cr] = cell(ref, "Remediate as follows.", spec["c"], note)
        else:
            r[col_cr] = cell(
                ref, prose + "\nRemediation requires operator judgement on this "
                "control — validate-only on the Red Hat family.", None, note)
        written += 1

    missing = [cid for cid in S if cid not in seen]
    if missing:
        print("SPEC control ids not found in the CSV:", missing, file=sys.stderr)
        return 1

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Red Hat cells written: {written}; Debian-only: {debianized}; "
          f"kept as-is: {untouched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
