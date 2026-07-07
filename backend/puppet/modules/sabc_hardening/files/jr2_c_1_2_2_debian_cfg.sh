#!/bin/bash
shopt -s globstar 2>/dev/null || true
if systemctl list-unit-files 2>/dev/null | grep -q '^dailyaidecheck\.timer'; then
  systemctl unmask dailyaidecheck.timer >/dev/null 2>&1
  systemctl enable --now dailyaidecheck.timer >/dev/null 2>&1 && exit 0
fi
if [ -x /usr/bin/aide.wrapper ]; then
  printf '0 5 * * * root /usr/bin/aide.wrapper --config /etc/aide/aide.conf --check\n' > /etc/cron.d/aide-check
else
  printf '0 5 * * * root /usr/sbin/aide --check\n' > /etc/cron.d/aide-check
fi
chmod 644 /etc/cron.d/aide-check
exit 0
