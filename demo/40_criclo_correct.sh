#!/usr/bin/env bash
# 40_criclo_correct.sh — the closed-loop CORRECTIVE, on the node.
#
# This is the remediation action for the filmed control. It demonstrates,
# tangibly on the server, what the platform decides after a drift is detected:
#
#   • If the node's closed loop is ON  → it REVERTS the intrusion by commenting
#     the offending line (leaving it as visible proof, stamped with WHO made the
#     change and WHY it was blocked), restores the compliant setting, reloads
#     sshd, and tells the author why their change was blocked.
#   • If the node's closed loop is OFF → it does NOT correct: the deviation is
#     kept as evidence and the author is told it was recorded but not reverted.
#     (This is the axis-independence behaviour, shown live.)
#
# The author ("who") is resolved from auditd — the same source the detection
# agent uses — falling back to the sudo user. Pass CRICLO_LOOP=on|off to select
# the branch (default on).
#
# Note: in production the closed loop's default corrective is a Puppet
# convergence that restores desired state; this script is the demo's on-node
# corrective, chosen because it makes the "who / why / proof" visible on camera.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/lib.sh"
require_root

TARGET=/etc/ssh/sshd_config
CONTROL="CIS L1 — SSH server: root login must be disabled (PermitRootLogin no)"
LOOP="${CRICLO_LOOP:-on}"
TS="$(date -u +%FT%TZ)"

actor="$(lookup_actor "$TARGET")"
c_info "Detected non-compliant directive on $TARGET, attributed to: $actor"
c_info "Violated control: $CONTROL"

if [ "$LOOP" != "on" ]; then
  c_step "Closed loop is OFF for this node — recording evidence only, no correction"
  msg="CRICLO: your change to $TARGET (PermitRootLogin yes) was DETECTED and recorded as evidence (attributed to $actor at $TS), but NOT reverted — the closed loop is disabled for this node. Enable it, or run Enforce, to correct."
  notify_actor "$actor" "$msg"
  c_ok "Evidence recorded; deviation left in place (loop disabled)."
  exit 0
fi

c_step "Closed loop is ON — reverting the intrusion"
backup_file "$TARGET"
note="CRICLO reverted $TS — set by ${actor}; BLOCKED: ${CONTROL}"

# 1) Comment the offending active line(s), keeping them as annotated proof.
sed -ri "s|^([[:space:]]*)(PermitRootLogin[[:space:]]+yes.*)$|\1# \2   # <-- ${note}|I" "$TARGET"

# 2) Restore the compliant setting (the only remaining ACTIVE directive wins).
printf 'PermitRootLogin no    # CRICLO enforced %s\n' "$TS" >> "$TARGET"

# 3) Apply — but never reload a broken config.
if ! reload_sshd_safe; then
  c_warn "Reverting: restoring pre-correction copy"; cp -a "$CRICLO_BACKUP_DIR/$CRICLO_RUN_TS$TARGET" "$TARGET"; reload_sshd_safe
  exit 1
fi

# 4) Tell the author why their change was blocked.
msg="CRICLO closed-loop remediation: your change to $TARGET (PermitRootLogin yes) was REVERTED. Reason: ${CONTROL}. Attributed to $actor at $TS. The offending line was commented out (kept as proof) and the compliant setting restored."
notify_actor "$actor" "$msg"

# 5) Show the proof for the camera.
c_step "Proof of correction (in $TARGET):"
grep -nE 'PermitRootLogin' "$TARGET" | sed 's/^/    /'
echo
c_ok "Intrusion corrected, attributed to '$actor', author notified. Re-scan to confirm the control is green again."
