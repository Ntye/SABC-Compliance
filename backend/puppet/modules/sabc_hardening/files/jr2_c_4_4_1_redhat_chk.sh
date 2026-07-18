#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q libpwquality >/dev/null 2>&1 || exit 1
conf() { awk -F= -v k="$1" '$1 ~ "^\\s*"k"\\s*$" {gsub(/ /,"",$2); v=$2} END {print v}' \
  /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null; }
ml=$(conf minlen); [ -n "$ml" ] && [ "$ml" -ge 14 ] || exit 1
mc=$(conf minclass)
if [ -n "$mc" ]; then [ "$mc" -ge 4 ] || exit 1
else
  for k in dcredit ucredit lcredit ocredit; do
    cv=$(conf $k); [ -n "$cv" ] && [ "$cv" -le -1 ] || exit 1
  done
fi
grep -Eq 'pam_pwquality\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth || exit 1
exit 0
