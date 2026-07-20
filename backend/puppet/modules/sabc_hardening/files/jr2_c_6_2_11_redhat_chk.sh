#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
umin=$(awk '/^\s*UID_MIN/{print $2}' /etc/login.defs); [ -n "$umin" ] || umin=1000
awk -F: -v m="$umin" '($3>=m && $7!~/(nologin|\/bin\/false)$/) {print $1":"$6}' /etc/passwd | \
while IFS=: read -r u h; do
  [ -d "$h" ] || exit 1
  set -- $(stat -Lc '%a %U %G' "$h")
mm=$1 o=$2 g=$3
  [ "$o" = "$u" ] || exit 1
  [ $(( 8#$mm & 8#0022 )) -eq 0 ] || exit 1
done
