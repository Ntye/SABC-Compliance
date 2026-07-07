#!/bin/bash
shopt -s globstar 2>/dev/null || true
v=$(grep -Ehs '^[[:space:]]*dictcheck[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
[ -n "$v" ] && [ "$v" -ge 1 ] && exit 0
exit 1
