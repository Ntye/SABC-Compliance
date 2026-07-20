#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
getent group sugroup >/dev/null 2>&1 || groupadd sugroup
if grep -Eq '^\s*#\s*auth\s+required\s+pam_wheel\.so' /etc/pam.d/su; then
  sed -ri 's/^\s*#\s*(auth\s+required\s+pam_wheel\.so).*/\1 use_uid group=sugroup/' /etc/pam.d/su
elif ! grep -Eq '^\s*auth\s+(required|requisite)\s+pam_wheel\.so' /etc/pam.d/su; then
  sed -ri '0,/^auth/s//auth            required        pam_wheel.so use_uid group=sugroup\n&/' /etc/pam.d/su
fi
exit 0
