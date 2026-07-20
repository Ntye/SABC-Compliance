#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ -e /etc/cron.hourly ] || exit 0
chown root:root /etc/cron.hourly
if [ -d /etc/cron.hourly ]; then chmod og-rwx /etc/cron.hourly; else chmod og-rwx,u-x /etc/cron.hourly; fi
