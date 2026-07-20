#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q aide >/dev/null 2>&1 || exit 1
grep -Ersq '^([^#]+\s)?(/usr/sbin/)?aide(\.wrapper)?\s(--check|.*--check)' \
  /etc/cron.d /etc/cron.daily /etc/cron.weekly /etc/crontab /var/spool/cron 2>/dev/null && exit 0
systemctl is-enabled aidecheck.timer 2>/dev/null | grep -q enabled && exit 0
exit 1
