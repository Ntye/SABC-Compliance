#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
grep -Eq '^\s*deny\s*=' /etc/security/faillock.conf 2>/dev/null \
  && sed -ri 's/^\s*(#\s*)?deny\s*=.*/deny = 5/' /etc/security/faillock.conf \
  || printf 'deny = 5\n' >> /etc/security/faillock.conf
grep -Eq '^\s*unlock_time\s*=' /etc/security/faillock.conf 2>/dev/null \
  && sed -ri 's/^\s*(#\s*)?unlock_time\s*=.*/unlock_time = 900/' /etc/security/faillock.conf \
  || printf 'unlock_time = 900\n' >> /etc/security/faillock.conf
if command -v authselect >/dev/null 2>&1 && authselect current >/dev/null 2>&1; then
  authselect enable-feature with-faillock 2>/dev/null || true
  authselect apply-changes 2>/dev/null || true
fi
exit 0
