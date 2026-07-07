#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q ntp >/dev/null 2>&1 || rpm -q ntpsec >/dev/null 2>&1 || exit 101
f=/etc/ntpsec/ntp.conf; [ -e "$f" ] || f=/etc/ntp.conf
[ -e "$f" ] || exit 1
for v in 4 6; do
  line=$(grep -Es "^[[:space:]]*restrict[[:space:]]+(-$v[[:space:]]+)?default\b" "$f" | head -1)
  [ -n "$line" ] || exit 1
  for opt in kod nomodify notrap nopeer noquery; do
    printf '%s' "$line" | grep -qw "$opt" || exit 1
  done
done
exit 0
