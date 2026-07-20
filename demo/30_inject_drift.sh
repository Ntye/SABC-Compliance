#!/usr/bin/env bash
# 30_inject_drift.sh — simulate the "intrusion" during the demo.
#
# Flips ONE hardened control on a WATCHED path so the detection agent sees it:
# it sets `PermitRootLogin yes` in /etc/ssh/sshd_config (a clear CIS L1
# violation). Run it while logged in as the "attacker" account so auditd
# attributes the change to that user:
#
#     ssh mallory@<node>
#     sudo /path/to/demo/30_inject_drift.sh
#
# Precondition for the closed-loop story: the node is ENFORCED, so the control
# is compliant (PermitRootLogin no) before this runs — this is the pass→fail
# deviation the loop then corrects.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/lib.sh"
require_root

TARGET=/etc/ssh/sshd_config
ACTOR="${SUDO_USER:-$(id -un)}"

c_step "Injecting drift as '$ACTOR': enabling root SSH login (CIS L1 violation)"
set_kv "$TARGET" PermitRootLogin yes
mkdir -p "$CRICLO_STATE_DIR"
printf '%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$ACTOR" "PermitRootLogin=yes" >> "$CRICLO_STATE_DIR/drift.log"

if reload_sshd_safe; then
  c_ok "Drift live. sshd now advertises: $(grep -E '^\s*PermitRootLogin' "$TARGET")"
  cat <<EOF

The detection agent should now forward a change event for $TARGET.
On the platform you should see, within a few seconds:
  • a new Detection Event for this node, attributed to '$ACTOR';
  • if the node's closed loop is ON  → an automatic remediation;
  • if the node's closed loop is OFF → the event recorded as evidence only.
EOF
else
  c_warn "sshd rejected the change; nothing reloaded."
fi
