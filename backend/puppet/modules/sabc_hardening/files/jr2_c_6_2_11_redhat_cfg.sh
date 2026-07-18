#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
umin=$(awk '/^\s*UID_MIN/{print $2}' /etc/login.defs); [ -n "$umin" ] || umin=1000
awk -F: -v m="$umin" '($3>=m && $7!~/(nologin|\/bin\/false)$/) {print $1":"$6}' /etc/passwd | \
while IFS=: read -r u h; do
  [ -d "$h" ] || { mkdir -p "$h"; chown "$u" "$h"; }
  chown "$u" "$h"
  chmod g-w,o-rwx "$h"
done
exit 0
