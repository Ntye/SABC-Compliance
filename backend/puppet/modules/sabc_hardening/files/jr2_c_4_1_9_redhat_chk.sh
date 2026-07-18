#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q at >/dev/null 2>&1 || exit 101
[ -f /etc/at.allow ] || exit 1
set -- $(stat -Lc '%a %U %G' /etc/at.allow)
m=$1 o=$2 g=$3
[ "$o" = root ] && [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
if [ -f /etc/at.deny ]; then
  set -- $(stat -Lc '%a %U %G' /etc/at.deny)
  m=$1 o=$2 g=$3
  [ "$o" = root ] && [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
fi
exit 0
