#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ -e /etc/cron.monthly ] || exit 0
chown root:root /etc/cron.monthly
if [ -d /etc/cron.monthly ]; then chmod og-rwx /etc/cron.monthly; else chmod og-rwx,u-x /etc/cron.monthly; fi
