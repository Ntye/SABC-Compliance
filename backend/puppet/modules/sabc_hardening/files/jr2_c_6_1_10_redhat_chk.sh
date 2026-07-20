#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
for f in /etc/security/opasswd /etc/security/opasswd.old; do
  [ -e "$f" ] || continue
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ "$o" = root ] && [ "$g" = root ] || exit 1
  [ $(( 8#$m & 8#0177 )) -eq 0 ] || exit 1
done
exit 0
