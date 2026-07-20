#!/usr/bin/env bash
# 00_prepare.sh — one-time demo prep on the managed node.
#
# Makes "who made the change" resolvable: installs auditd and adds a watch rule
# (key "sabc-watch") on the files the detection agent monitors, so the agent's
# ausearch lookup can attribute a change to a real user. Optionally creates a
# demo operator account to play the "who" in the film.
#
# Safe and reversible: auditd rules are removed by 20_restore.sh.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/lib.sh"
require_root

DEMO_USER="${DEMO_USER:-mallory}"          # the actor shown in the correction proof
MAKE_USER="${MAKE_USER:-1}"                 # set 0 to skip creating the demo account

c_step "Installing auditd (best-effort; actor attribution degrades gracefully without it)"
if ! command -v auditctl >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get update -qq && apt-get install -y -qq auditd audispd-plugins
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y -q audit
  fi
fi
systemctl enable --now auditd 2>/dev/null || service auditd start 2>/dev/null || true

c_step "Adding audit watch rules (key=$AUDIT_KEY) on the detection agent's paths"
RULES=/etc/audit/rules.d/criclo-demo.rules
backup_file "$RULES"
cat > "$RULES" <<EOF
# CRICLO demo — record writes to the compliance-critical config so the platform
# can attribute each change to a user. Removed by demo/20_restore.sh.
-w /etc/ssh/sshd_config -p wa -k $AUDIT_KEY
-w /etc/sudoers -p wa -k $AUDIT_KEY
-w /etc/passwd -p wa -k $AUDIT_KEY
-w /etc/group -p wa -k $AUDIT_KEY
-w /etc/pam.d/ -p wa -k $AUDIT_KEY
EOF
augenrules --load 2>/dev/null || auditctl -R "$RULES" 2>/dev/null || true
auditctl -l | grep -q "$AUDIT_KEY" && c_ok "audit watch active" || c_warn "audit rules not loaded (attribution will fall back to sudo user)"

if [ "$MAKE_USER" = "1" ] && ! id "$DEMO_USER" >/dev/null 2>&1; then
  c_step "Creating demo operator '$DEMO_USER' (sudo-capable) to act as the change author"
  useradd -m -s /bin/bash "$DEMO_USER"
  usermod -aG sudo "$DEMO_USER" 2>/dev/null || usermod -aG wheel "$DEMO_USER" 2>/dev/null || true
  echo "$DEMO_USER:Demo-CRICLO-2026" | chpasswd
  c_ok "user '$DEMO_USER' created (password: Demo-CRICLO-2026) — change or delete after the demo"
fi

c_ok "Prep complete. Next: run 10_make_noncompliant.sh, scan from the platform, then film."
