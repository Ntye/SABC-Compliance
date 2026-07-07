#!/bin/bash
shopt -s globstar 2>/dev/null || true
vals=$(grep -rhoPs 'timestamp_timeout[[:space:]]*=[[:space:]]*\K-?[0-9]+' /etc/sudoers /etc/sudoers.d 2>/dev/null)
if [ -z "$vals" ]; then
  d=$(sudo -V 2>/dev/null | grep -oP 'Authentication timestamp timeout:[[:space:]]*\K-?[0-9]+')
  [ -n "$d" ] && [ "$d" -ge 0 ] && [ "$d" -le 15 ] && exit 0
  exit 1
fi
for v in $vals; do
  [ "$v" -ge 0 ] && [ "$v" -le 15 ] || exit 1
done
exit 0
