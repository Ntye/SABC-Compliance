#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
found=0
for f in /etc/ssh/ssh_host_*_key; do
  [ -e "$f" ] || continue
  found=1
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ "$o" = root ] || exit 1
  if [ "$g" = "ssh_keys" ]; then
    [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
  else
    [ "$g" = root ] && [ $(( 8#$m & 8#0177 )) -eq 0 ] || exit 1
  fi
done
[ "$found" -eq 1 ] && exit 0 || exit 101
