#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
d=$(awk -F= '/^\s*deny\s*=/ {gsub(/ /,"",$2); print $2}' /etc/security/faillock.conf 2>/dev/null | tail -n1)
u=$(awk -F= '/^\s*unlock_time\s*=/ {gsub(/ /,"",$2); print $2}' /etc/security/faillock.conf 2>/dev/null | tail -n1)
[ -n "$d" ] && [ "$d" -ge 1 ] && [ "$d" -le 5 ] || exit 1
[ -n "$u" ] && { [ "$u" -eq 0 ] || [ "$u" -ge 900 ]; } || exit 1
grep -Eq 'pam_faillock\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth || exit 1
exit 0
