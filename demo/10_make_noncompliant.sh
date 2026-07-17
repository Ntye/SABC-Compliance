#!/usr/bin/env bash
# 10_make_noncompliant.sh — establish a reproducible ~49% compliance baseline.
#
# Applies a curated set of CIS-flagged-but-SAFE weakenings so the "before" score
# is stable across takes. It deliberately does NOT touch anything that would
# affect the key aspects of the server: your SSH session stays up (sshd is only
# reloaded after `sshd -t` passes, and the demo drop-in is auto-removed if it
# would ever make the config invalid), sudo keeps working, networking and the
# hostname/IP are untouched, no service is removed. Every file is backed up
# first; demo/20_restore.sh undoes ALL of it (files, directory modes, new
# drop-ins) via the backup tree and the recorded undo log.
#
# CALIBRATION: run this, then scan the node from the platform. If you are not at
# ~49%, toggle the KNOBS below (0/1) and re-run — each group is independent.
# Overshot (too low)? Set a KNOB to 0, run 20_restore.sh, then re-run.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/lib.sh"
require_root

# ── Calibration knobs — flip to 0 to skip a group, then re-scan ──────────────
KNOB_SSH=${KNOB_SSH:-1}              # ~16 SSH controls (§4.2) — via a winning drop-in
KNOB_SYSCTL=${KNOB_SYSCTL:-1}       # ~12 kernel/network controls (§1.4, §3) — last-loading + runtime
KNOB_LOGINDEFS=${KNOB_LOGINDEFS:-1} # ~5 password-policy / umask / hashing controls (§4.4/§4.5)
KNOB_BANNER=${KNOB_BANNER:-1}       # ~5 banner content + permission controls (§1.6)
KNOB_CRON=${KNOB_CRON:-1}           # ~8 cron permission / restriction controls (§4.1)
KNOB_FILEPERMS=${KNOB_FILEPERMS:-1} # ~12 system-file permission controls (§6.1)
KNOB_LOGGING=${KNOB_LOGGING:-1}     # ~3 journald / rsyslog controls (§5.1)
KNOB_PERMS=${KNOB_PERMS:-1}         # ~2 extra config-file permission controls

mkdir -p "$CRICLO_STATE_DIR"
echo "CRICLO demo baseline — run $CRICLO_RUN_TS" > "$CRICLO_STATE_DIR/last_baseline"

# ── §4.2 SSH ─────────────────────────────────────────────────────────────────
if [ "$KNOB_SSH" = 1 ]; then
  c_step "SSH: relaxing hardened directives (root login, crypto, banners, limits)"
  f=/etc/ssh/sshd_config
  set_kv "$f" PermitRootLogin yes
  set_kv "$f" X11Forwarding yes
  set_kv "$f" AllowTcpForwarding yes
  set_kv "$f" MaxAuthTries 10
  set_kv "$f" LoginGraceTime 120
  set_kv "$f" ClientAliveInterval 0
  set_kv "$f" MaxSessions 20
  set_kv "$f" LogLevel INFO          # CIS wants VERBOSE
  set_kv "$f" Banner none

  # Ubuntu reads /etc/ssh/sshd_config.d/*.conf FIRST (first-match wins), so the
  # hardening drop-ins override edits to the main file. A 00- drop-in is read
  # before them and wins. Crypto uses "+" so STRONG algorithms stay available
  # (your session is never cut) while a weak one is added for CIS to flag.
  dropd=/etc/ssh/sshd_config.d
  if [ -d "$dropd" ]; then
    df="$dropd/00-criclo-demo.conf"
    cat > "$df" <<'EOF'
# CRICLO demo — intentionally weak SSH. Removed by demo/20_restore.sh.
LogLevel INFO
PermitRootLogin yes
HostbasedAuthentication yes
PermitEmptyPasswords yes
IgnoreRhosts no
PermitUserEnvironment yes
MaxAuthTries 10
LoginGraceTime 120
MaxSessions 20
MaxStartups 100
ClientAliveInterval 0
ClientAliveCountMax 3
Banner none
Ciphers +aes128-cbc
MACs +hmac-sha1
KexAlgorithms +diffie-hellman-group14-sha1
EOF
  fi

  if ! reload_sshd_safe; then
    c_warn "sshd config invalid with the demo weakenings — reverting SSH group to keep the box reachable"
    rm -f "${dropd:-/tmp}/00-criclo-demo.conf" 2>/dev/null || true
    [ -e "$CRICLO_BACKUP_DIR/$CRICLO_RUN_TS$f" ] && cp -a "$CRICLO_BACKUP_DIR/$CRICLO_RUN_TS$f" "$f"
    reload_sshd_safe || c_warn "check sshd manually"
  fi
fi

# ── §1.4 / §3 kernel + network sysctls ───────────────────────────────────────
if [ "$KNOB_SYSCTL" = 1 ]; then
  c_step "Kernel/network: insecure sysctl values (ASLR off, redirects/forwarding on)"
  # Named to load AFTER /etc/sysctl.d/99-sysctl.conf (which re-applies the
  # hardened values), so ours win; and forced onto the running kernel with -w
  # so the scan (which reads the live value) sees the insecure setting.
  f=/etc/sysctl.d/99-zzz-criclo-demo.conf
  cat > "$f" <<'EOF'
# CRICLO demo — intentionally insecure. Removed by demo/20_restore.sh.
kernel.randomize_va_space = 0
net.ipv4.ip_forward = 1
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
net.ipv4.conf.all.accept_redirects = 1
net.ipv4.conf.default.accept_redirects = 1
net.ipv4.conf.all.secure_redirects = 1
net.ipv4.conf.default.secure_redirects = 1
net.ipv4.conf.all.send_redirects = 1
net.ipv4.conf.default.send_redirects = 1
net.ipv4.conf.all.accept_source_route = 1
net.ipv4.conf.default.accept_source_route = 1
net.ipv4.conf.all.log_martians = 0
net.ipv4.conf.default.log_martians = 0
net.ipv4.icmp_echo_ignore_broadcasts = 0
net.ipv4.icmp_ignore_bogus_error_responses = 0
net.ipv4.tcp_syncookies = 0
net.ipv6.conf.all.accept_ra = 1
net.ipv6.conf.default.accept_ra = 1
net.ipv6.conf.all.accept_redirects = 1
net.ipv6.conf.default.accept_redirects = 1
net.ipv6.conf.all.accept_source_route = 1
net.ipv6.conf.default.accept_source_route = 1
EOF
  # Apply the file, then force each key onto the live kernel.
  sysctl --system >/dev/null 2>&1 || true
  grep -vE '^\s*#|^\s*$' "$f" | sed 's/ *= */=/' | while IFS= read -r kv; do
    sysctl -w "$kv" >/dev/null 2>&1 || true
  done
  undo_add "sysctl --system >/dev/null 2>&1 || true"
  c_ok "sysctl values applied (file + live)"
fi

# ── §4.4/§4.5 password policy ─────────────────────────────────────────────────
if [ "$KNOB_LOGINDEFS" = 1 ]; then
  c_step "Password policy: weakening /etc/login.defs (aging, umask, hashing)"
  f=/etc/login.defs
  set_kv "$f" PASS_MAX_DAYS 99999 $'\t'
  set_kv "$f" PASS_MIN_DAYS 0 $'\t'
  set_kv "$f" UMASK 022 $'\t\t'
  set_kv "$f" ENCRYPT_METHOD MD5 $'\t'   # CIS wants SHA512/yescrypt → §4.4.4 fails
  c_ok "login.defs weakened"
fi

# ── §1.6 banners ─────────────────────────────────────────────────────────────
if [ "$KNOB_BANNER" = 1 ]; then
  c_step "Banners: writing OS-revealing content + loosening perms (CIS wants neither)"
  # CIS fails /etc/issue(.net) when they contain the \m \r \s \v OS escapes, and
  # fails the perm checks when they are group/other-writable. Empty files PASS,
  # so we write content rather than clearing.
  for f in /etc/issue /etc/issue.net /etc/motd; do
    backup_file "$f"; printf 'Welcome to \\S \\r (\\m) — \\v\n' > "$f"; chmod o+w "$f"
  done
  c_ok "banners weakened"
fi

# ── §4.1 cron ────────────────────────────────────────────────────────────────
if [ "$KNOB_CRON" = 1 ]; then
  c_step "Cron: loosening permissions and restriction files"
  [ -e /etc/crontab ] && { backup_file /etc/crontab; chmod o+r /etc/crontab; }
  for d in /etc/cron.hourly /etc/cron.daily /etc/cron.weekly /etc/cron.monthly /etc/cron.d; do
    [ -d "$d" ] || continue
    undo_add "chmod $(stat -c %a "$d") $d"   # directory mode is not restored from the file backup
    chmod o+rwx "$d"
  done
  # CIS wants cron/at restricted via an allow-list; remove it and add a deny file.
  for f in /etc/cron.allow /etc/at.allow; do [ -e "$f" ] && { backup_file "$f"; rm -f "$f"; }; done
  for f in /etc/cron.deny /etc/at.deny;  do [ -e "$f" ] || { : > "$f"; chmod o+rw "$f"; undo_add "rm -f $f"; }; done
  c_ok "cron weakened"
fi

# ── §6.1 system-file permissions ─────────────────────────────────────────────
if [ "$KNOB_FILEPERMS" = 1 ]; then
  c_step "System files: loosening permissions CIS expects locked down"
  # World-writable on the account databases and shells (owner still root — login
  # and sudo keep working; this is exactly the finding being demonstrated).
  for f in /etc/passwd /etc/passwd- /etc/group /etc/group- /etc/shells; do
    [ -e "$f" ] && { backup_file "$f"; chmod o+w "$f"; }
  done
  # World-readable on the shadow family (exposes hashes — demo only, and fully
  # reverted by 20_restore.sh, which restores the saved mode).
  for f in /etc/shadow /etc/shadow- /etc/gshadow /etc/gshadow- /etc/security/opasswd /etc/opasswd; do
    [ -e "$f" ] && { backup_file "$f"; chmod o+r "$f"; }
  done
  # A world-writable file (no sticky bit) and an unowned file — §6.1.11 / §6.1.12.
  ww=/etc/criclo-demo-worldwritable; touch "$ww"; chmod 0666 "$ww"; undo_add "rm -f $ww"
  uo=/etc/criclo-demo-unowned;       touch "$uo"; chown 9998:9998 "$uo" 2>/dev/null || true; undo_add "rm -f $uo"
  c_ok "file permissions loosened"
fi

# ── §5.1 logging ─────────────────────────────────────────────────────────────
if [ "$KNOB_LOGGING" = 1 ]; then
  c_step "Logging: weakening journald + rsyslog settings"
  jc=/etc/systemd/journald.conf
  [ -e "$jc" ] && { set_kv "$jc" Storage volatile "="; set_kv "$jc" Compress no "="; }
  rc=/etc/rsyslog.conf
  if [ -e "$rc" ] && ! grep -q 'criclo-demo' "$rc"; then
    backup_file "$rc"; printf '\n$FileCreateMode 0644 # criclo-demo\n' >> "$rc"   # CIS wants 0640
  fi
  c_ok "logging weakened"
fi

# ── extra config-file permissions ────────────────────────────────────────────
if [ "$KNOB_PERMS" = 1 ]; then
  c_step "Permissions: loosening a couple more config files CIS expects locked down"
  for f in /etc/ssh/sshd_config; do [ -e "$f" ] && { backup_file "$f"; chmod o+r "$f"; }; done
  c_ok "permissions loosened"
fi

cat <<EOF

$(c_ok "Baseline applied. Backups in $CRICLO_BACKUP_DIR/$CRICLO_RUN_TS")

Next steps:
  1. In the platform UI, run a scan of this node.
  2. Read the score. Target ~49%. If still too HIGH, all knobs are already on —
     re-run after a scan to confirm SSH/sysctl took effect. If too LOW, set a
     KNOB to 0, run 20_restore.sh, then re-run.

Undo everything:  sudo demo/20_restore.sh
EOF
