#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q chrony >/dev/null 2>&1 || exit 0
if ! grep -Eq '^\s*OPTIONS=.*-u\s+chrony' /etc/sysconfig/chronyd 2>/dev/null; then
  printf 'OPTIONS="-u chrony"\n' > /etc/sysconfig/chronyd
fi
systemctl try-restart chronyd.service 2>/dev/null || true
exit 0
