#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W libpam-pwquality >/dev/null 2>&1 || exit 1
v=$(grep -Ehs '^[[:space:]]*minlen[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
[ -n "$v" ] && [ "$v" -ge 14 ] || exit 1
c=$(grep -Ehs '^[[:space:]]*minclass[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
[ -n "$c" ] && [ "$c" -ge 4 ] || exit 1
exit 0
