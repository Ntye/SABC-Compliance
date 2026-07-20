#!/bin/bash
shopt -s globstar 2>/dev/null || true
if dpkg-query -W ntpsec >/dev/null 2>&1; then u=ntpsec
elif dpkg-query -W ntp >/dev/null 2>&1; then u=ntp
else exit 0; fi
systemctl unmask "$u" >/dev/null 2>&1
systemctl enable --now "$u" >/dev/null 2>&1
exit 0
