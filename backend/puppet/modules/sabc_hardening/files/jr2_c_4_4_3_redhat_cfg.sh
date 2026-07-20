#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
if [ -f /etc/security/pwhistory.conf ]; then
  grep -Eq '^\s*remember\s*=' /etc/security/pwhistory.conf \
    && sed -ri 's/^\s*(#\s*)?remember\s*=.*/remember = 5/' /etc/security/pwhistory.conf \
    || printf 'remember = 5\n' >> /etc/security/pwhistory.conf
else
  printf 'remember = 5\n' > /etc/security/pwhistory.conf
fi
if command -v authselect >/dev/null 2>&1 && authselect current >/dev/null 2>&1; then
  authselect enable-feature with-pwhistory 2>/dev/null || true
  authselect apply-changes 2>/dev/null || true
fi
exit 0
