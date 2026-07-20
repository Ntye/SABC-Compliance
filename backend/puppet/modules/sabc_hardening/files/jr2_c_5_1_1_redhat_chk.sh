#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
find -L /var/log -type f -perm /o+w ! -path '*/journal/*' 2>/dev/null | grep -q . && exit 1
for f in /var/log/secure /var/log/messages /var/log/maillog /var/log/cron; do
  [ -e "$f" ] || continue
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
done
exit 0
