#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ -e /etc/cron.weekly ] || exit 0
chown root:root /etc/cron.weekly
if [ -d /etc/cron.weekly ]; then chmod og-rwx /etc/cron.weekly; else chmod og-rwx,u-x /etc/cron.weekly; fi
