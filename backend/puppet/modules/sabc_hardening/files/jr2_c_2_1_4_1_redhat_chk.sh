#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q ntp >/dev/null 2>&1 || exit 101
c=$(grep -Ec '^\s*restrict\s+(-4\s+|-6\s+)?default\s' /etc/ntp.conf 2>/dev/null)
[ "$c" -ge 2 ]
