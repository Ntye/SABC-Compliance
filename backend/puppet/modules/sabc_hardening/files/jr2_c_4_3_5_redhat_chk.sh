#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
vals=$(grep -Ersho 'timestamp_timeout\s*=\s*-?[0-9]+' /etc/sudoers /etc/sudoers.d 2>/dev/null | grep -Eo '[-0-9]+')
[ -z "$vals" ] && exit 0
for v in $vals; do
  [ "$v" -ge 0 ] && [ "$v" -le 15 ] || exit 1
done
exit 0
