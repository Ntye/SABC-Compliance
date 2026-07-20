#!/bin/bash
shopt -s globstar 2>/dev/null || true
getent group sugroup >/dev/null 2>&1 || groupadd sugroup
grep -Eqs '^[[:space:]]*auth[[:space:]]+(required|requisite)[[:space:]]+pam_wheel\.so' /etc/pam.d/su || \
  sed -i '/^auth[[:space:]]\+sufficient[[:space:]]\+pam_rootok\.so/a auth       required   pam_wheel.so use_uid group=sugroup' /etc/pam.d/su
exit 0
