#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W ntp >/dev/null 2>&1 || dpkg-query -W ntpsec >/dev/null 2>&1 || exit 101
for u in ntp ntpsec; do
  if systemctl is-enabled "$u" 2>/dev/null | grep -q '^enabled'; then
    systemctl is-active "$u" 2>/dev/null | grep -qx active && exit 0
  fi
done
exit 1
