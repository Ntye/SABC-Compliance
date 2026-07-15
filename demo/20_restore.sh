#!/usr/bin/env bash
# 20_restore.sh — undo everything the demo scripts changed.
#
# Restores every backed-up file from the most recent backup set, removes the
# demo sysctl drop-in and audit rules, and reloads sshd/sysctl. Use it between
# takes or to hand the server back clean.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/lib.sh"
require_root

LATEST="$(ls -1dt "$CRICLO_BACKUP_DIR"/*/ 2>/dev/null | head -n1 || true)"

if [ -n "$LATEST" ]; then
  c_step "Restoring files from $LATEST"
  # Walk the backup tree and copy each file back to its absolute path.
  ( cd "$LATEST" && find . -type f -print0 | while IFS= read -r -d '' rel; do
      dst="/${rel#./}"; mkdir -p "$(dirname "$dst")"; cp -a "$rel" "$dst"; echo "  restored $dst"
    done )
else
  c_warn "No backup set found in $CRICLO_BACKUP_DIR — restoring known drop-ins only"
fi

c_step "Removing demo drop-ins"
rm -f /etc/sysctl.d/99-criclo-demo.conf && sysctl --system >/dev/null 2>&1 || true
rm -f /etc/audit/rules.d/criclo-demo.rules && { augenrules --load 2>/dev/null || true; }
c_ok "drop-ins removed"

c_step "Reloading services"
reload_sshd_safe || c_warn "check sshd manually"
c_ok "Restore complete. Re-scan from the platform to confirm the score returns to baseline."
