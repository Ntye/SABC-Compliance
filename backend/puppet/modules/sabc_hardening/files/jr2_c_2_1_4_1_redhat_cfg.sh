#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q ntp >/dev/null 2>&1 || exit 0
grep -Eq '^\s*restrict\s+(-4\s+)?default' /etc/ntp.conf || \
  printf 'restrict -4 default kod nomodify notrap nopeer noquery\n' >> /etc/ntp.conf
grep -Eq '^\s*restrict\s+-6\s+default' /etc/ntp.conf || \
  printf 'restrict -6 default kod nomodify notrap nopeer noquery\n' >> /etc/ntp.conf
systemctl try-restart ntpd.service 2>/dev/null || true
exit 0
