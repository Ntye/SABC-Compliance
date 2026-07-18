#!/bin/bash
shopt -s globstar 2>/dev/null || true
d=$(grep -Ehs '^[[:space:]]*deny[[:space:]]*=' /etc/security/faillock.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
[ -n "$d" ] && [ "$d" -ge 1 ] && [ "$d" -le 5 ] || exit 1
u=$(grep -Ehs '^[[:space:]]*unlock_time[[:space:]]*=' /etc/security/faillock.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
[ -n "$u" ] || exit 1
[ "$u" -eq 0 ] || [ "$u" -ge 900 ] || exit 1
grep -qs 'pam_faillock.so' /etc/pam.d/common-auth || exit 1
exit 0
