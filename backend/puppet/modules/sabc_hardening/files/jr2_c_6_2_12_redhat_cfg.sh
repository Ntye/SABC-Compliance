#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
umin=$(awk '/^\s*UID_MIN/{print $2}' /etc/login.defs); [ -n "$umin" ] || umin=1000
awk -F: -v m="$umin" '($3>=m && $7!~/(nologin|\/bin\/false)$/) {print $6}' /etc/passwd | \
while read -r h; do
  [ -d "$h" ] || continue
  find "$h" -maxdepth 1 -name '.*' -type f -perm /go+w -exec chmod go-w {} + 2>/dev/null
done
exit 0
