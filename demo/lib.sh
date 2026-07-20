#!/usr/bin/env bash
# Shared helpers for the CRICLO demo scripts. Source this; do not execute it.
# All scripts run ON THE MANAGED NODE (Debian/Ubuntu family), as root.
set -euo pipefail

CRICLO_BACKUP_DIR="/var/backups/criclo-demo"
CRICLO_STATE_DIR="/var/lib/criclo-demo"
AUDIT_KEY="sabc-watch"                 # must match the detection agent's ausearch key
: "${CRICLO_RUN_TS:=$(date -u +%Y%m%dT%H%M%SZ)}"

c_info() { printf '\033[1;36m[CRICLO]\033[0m %s\n' "$*"; }
c_ok()   { printf '\033[1;32m[  OK  ]\033[0m %s\n' "$*"; }
c_warn() { printf '\033[1;33m[ WARN ]\033[0m %s\n' "$*"; }
c_step() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

require_root() { [ "$(id -u)" -eq 0 ] || { echo "This script must run as root (use sudo)."; exit 1; }; }

# The ssh unit is 'ssh' on Debian/Ubuntu, 'sshd' on RHEL-family.
ssh_service() {
  if systemctl list-unit-files 2>/dev/null | grep -q '^sshd\.service'; then echo sshd; else echo ssh; fi
}

# Copy a file once per run into a timestamped backup tree so 20_restore.sh can undo it.
backup_file() {
  local f="$1" d="$CRICLO_BACKUP_DIR/$CRICLO_RUN_TS"
  mkdir -p "$d"
  if [ -e "$f" ] && [ ! -e "$d$f" ]; then
    mkdir -p "$(dirname "$d$f")"
    cp -a "$f" "$d$f"
  fi
}

# Record a reverse command so 20_restore.sh can undo a non-file change
# (directory mode, a newly-created drop-in, a stopped service). File-content and
# file-mode changes are already reverted from the backup tree; use this only for
# things a file copy cannot restore.
undo_add() {
  mkdir -p "$CRICLO_STATE_DIR"
  printf '%s\n' "$*" >> "$CRICLO_STATE_DIR/undo.sh"
}

# Apply an sshd config change to the RUNNING daemon safely — or not at all.
#
# NEVER restarts sshd. A reload (SIGHUP) makes sshd re-read its config for new
# connections without ever dropping the listener, so the box stays reachable
# even if the new config is wrong. A *restart* tears down the listener, and a
# config that passes `sshd -t` but misbehaves at runtime (or a socket-activated
# unit that doesn't come back) then leaves the port closed — the one way to lose
# a remote box, and exactly the lockout this demo must never cause. If the
# config is invalid we do not touch the daemon at all.
reload_sshd_safe() {
  if ! sshd -t 2>/tmp/criclo_sshd_test; then
    c_warn "sshd -t reported an INVALID config; NOT touching the running daemon. Details:"
    cat /tmp/criclo_sshd_test
    return 1
  fi
  # Reload only — never restart. A missing/failed reload verb is harmless: the
  # running daemon keeps serving and the scan reads the on-disk config anyway.
  if systemctl reload "$(ssh_service)" 2>/dev/null; then
    c_ok "sshd configuration valid — reloaded (listener never dropped)"
  else
    c_warn "could not reload sshd — left the running daemon untouched (on-disk config is what the scan reads)"
  fi
}

# Idempotently set "key<sep>value" in a simple key/value file (sshd_config,
# login.defs, sysctl.d). Removes any existing active OR commented directive for
# the key first, then appends the new one.
set_kv() {
  local file="$1" key="$2" val="$3" sep="${4:- }"
  backup_file "$file"
  touch "$file"
  grep -vE "^[[:space:]]*#?[[:space:]]*${key}([[:space:]]|=)" "$file" > "${file}.criclo.tmp" 2>/dev/null || true
  mv "${file}.criclo.tmp" "$file"
  printf '%s%s%s\n' "$key" "$sep" "$val" >> "$file"
}

# Resolve WHO last wrote to a path — the same source the detection agent uses
# (auditd). Falls back to the invoking sudo user, then the file owner.
lookup_actor() {
  local path="$1" auid="" name=""
  if command -v ausearch >/dev/null 2>&1; then
    auid="$(ausearch -f "$path" -k "$AUDIT_KEY" --raw -ts recent 2>/dev/null \
            | grep -oE 'auid=[0-9]+' | tail -n1 | cut -d= -f2 || true)"
    if [ -n "$auid" ] && [ "$auid" != "4294967295" ]; then
      name="$(getent passwd "$auid" | cut -d: -f1 || true)"
    fi
  fi
  [ -z "$name" ] && name="${SUDO_USER:-}"
  [ -z "$name" ] && name="$(stat -c %U "$path" 2>/dev/null || echo unknown)"
  echo "$name"
}

# Notify a logged-in user (and the audit log) why their change was blocked.
notify_actor() {
  local actor="$1" message="$2"
  logger -t criclo "$message"
  mkdir -p "$CRICLO_STATE_DIR"
  printf '%s  %s\n' "$(date -u +%FT%TZ)" "$message" >> "$CRICLO_STATE_DIR/notices.log"
  # Broadcast to the actor's terminals (visible in their SSH session) — and to
  # all terminals via wall, which is the most reliable on-camera signal.
  if command -v write >/dev/null 2>&1 && [ -n "$actor" ] && who | grep -q "^$actor\b"; then
    printf '%s\n' "$message" | write "$actor" 2>/dev/null || true
  fi
  command -v wall >/dev/null 2>&1 && printf 'CRICLO closed-loop remediation\n%s\n' "$message" | wall 2>/dev/null || true
}
