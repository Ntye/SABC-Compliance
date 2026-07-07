#!/bin/bash
shopt -s globstar 2>/dev/null || true
if rpm -q ntpsec >/dev/null 2>&1; then u=ntpsec
elif rpm -q ntp >/dev/null 2>&1; then u=ntp
else exit 0; fi
systemctl unmask "$u" >/dev/null 2>&1
systemctl enable --now "$u" >/dev/null 2>&1
exit 0
