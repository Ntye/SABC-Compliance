#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
f=/etc/motd
[ -e "$f" ] || exit 0
grep -Eiq '(\\v|\\r|\\m|\\s)' "$f" && exit 1
for tok in $(. /etc/os-release; echo "$ID"); do
  grep -iq "$tok" "$f" && exit 1
done
exit 0
