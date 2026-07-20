#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W gdm3 >/dev/null 2>&1 || exit 0
for f in /etc/gdm3/custom.conf /etc/gdm/custom.conf; do
  [ -e "$f" ] && sed -ri 's/^[[:space:]]*Enable[[:space:]]*=[[:space:]]*true/Enable=false/I' "$f"
done
exit 0
