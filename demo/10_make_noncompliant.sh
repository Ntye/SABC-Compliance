#!/usr/bin/env bash
# 10_make_noncompliant.sh — establish a reproducible ~49% compliance baseline.
#
# Applies a curated set of CIS-flagged-but-SAFE weakenings so the "before" score
# is stable across takes. It deliberately does NOT touch anything that would
# affect the key aspects of the server: your SSH session stays up, sudo keeps
# working, networking and the hostname/IP are untouched, no service is removed.
# Every file is backed up first; demo/20_restore.sh undoes all of it.
#
# CALIBRATION: run this, then scan the node from the platform. If you are not at
# ~49%, toggle the KNOBS below (0/1) and re-run — each group is independent.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/lib.sh"
require_root

# ── Calibration knobs — flip to 0 to skip a group, then re-scan ──────────────
KNOB_SSH=${KNOB_SSH:-1}          # ~10 SSH controls
KNOB_SYSCTL=${KNOB_SYSCTL:-1}    # ~12 kernel/network controls (incl. ASLR off)
KNOB_LOGINDEFS=${KNOB_LOGINDEFS:-1}  # ~4 password-policy / umask controls
KNOB_BANNER=${KNOB_BANNER:-1}    # ~3 warning-banner controls
KNOB_PERMS=${KNOB_PERMS:-1}      # ~3 file-permission controls

echo "CRICLO demo baseline — run $CRICLO_RUN_TS" | tee "$CRICLO_STATE_DIR/last_baseline" >/dev/null 2>&1 || mkdir -p "$CRICLO_STATE_DIR"

if [ "$KNOB_SSH" = 1 ]; then
  c_step "SSH: relaxing hardened directives (root login, forwarding, banners, crypto)"
  f=/etc/ssh/sshd_config
  set_kv "$f" PermitRootLogin yes
  set_kv "$f" X11Forwarding yes
  set_kv "$f" AllowTcpForwarding yes
  set_kv "$f" MaxAuthTries 10
  set_kv "$f" LoginGraceTime 120
  set_kv "$f" ClientAliveInterval 0
  set_kv "$f" ClientAliveCountMax 3
  set_kv "$f" MaxSessions 10
  set_kv "$f" LogLevel INFO          # CIS wants VERBOSE
  set_kv "$f" Banner none
  # Drop any explicit strong-crypto allow-lists → falls back to defaults (a CIS finding)
  for k in Ciphers MACs KexAlgorithms; do
    grep -vE "^[[:space:]]*#?[[:space:]]*$k[[:space:]]" "$f" > "$f.criclo.tmp" && mv "$f.criclo.tmp" "$f"
  done
  reload_sshd_safe || { c_warn "reverting SSH group"; cp -a "$CRICLO_BACKUP_DIR/$CRICLO_RUN_TS/etc/ssh/sshd_config" "$f"; reload_sshd_safe; }
fi

if [ "$KNOB_SYSCTL" = 1 ]; then
  c_step "Kernel/network: writing insecure sysctl values (ASLR off, redirects/forwarding on)"
  f=/etc/sysctl.d/99-criclo-demo.conf
  backup_file "$f"
  cat > "$f" <<'EOF'
# CRICLO demo — intentionally insecure. Removed by demo/20_restore.sh.
kernel.randomize_va_space = 0
net.ipv4.ip_forward = 1
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.all.accept_redirects = 1
net.ipv4.conf.default.accept_redirects = 1
net.ipv4.conf.all.secure_redirects = 1
net.ipv4.conf.all.send_redirects = 1
net.ipv4.conf.all.accept_source_route = 1
net.ipv4.conf.all.log_martians = 0
net.ipv4.icmp_echo_ignore_broadcasts = 0
net.ipv6.conf.all.accept_ra = 1
net.ipv6.conf.all.accept_redirects = 1
EOF
  sysctl --system >/dev/null 2>&1 || true
  c_ok "sysctl values applied"
fi

if [ "$KNOB_LOGINDEFS" = 1 ]; then
  c_step "Password policy: weakening /etc/login.defs (aging + umask)"
  f=/etc/login.defs
  set_kv "$f" PASS_MAX_DAYS 99999 $'\t'
  set_kv "$f" PASS_MIN_DAYS 0 $'\t'
  set_kv "$f" UMASK 022 $'\t\t'
  c_ok "login.defs weakened"
fi

if [ "$KNOB_BANNER" = 1 ]; then
  c_step "Banners: clearing the legal warning banners CIS requires"
  for f in /etc/issue /etc/issue.net /etc/motd; do backup_file "$f"; : > "$f"; done
  c_ok "banners cleared"
fi

if [ "$KNOB_PERMS" = 1 ]; then
  c_step "Permissions: loosening a few config files CIS expects locked down"
  for f in /etc/crontab /etc/ssh/sshd_config; do [ -e "$f" ] && { backup_file "$f"; chmod o+r "$f"; }; done
  c_ok "permissions loosened"
fi

cat <<EOF

$(c_ok "Baseline applied. Backups in $CRICLO_BACKUP_DIR/$CRICLO_RUN_TS")

Next steps:
  1. In the platform UI, run a scan of this node.
  2. Read the score. Target ~49%. If higher, enable more KNOBs; if lower,
     set a KNOB to 0 and re-run (or restore first with 20_restore.sh).
  3. When you are happy with the 'before' score, start filming.

Undo everything:  sudo demo/20_restore.sh
EOF
