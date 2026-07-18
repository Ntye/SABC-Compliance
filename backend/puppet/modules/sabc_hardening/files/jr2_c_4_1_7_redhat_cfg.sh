#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ -e /etc/cron.d ] || exit 0
chown root:root /etc/cron.d
if [ -d /etc/cron.d ]; then chmod og-rwx /etc/cron.d; else chmod og-rwx,u-x /etc/cron.d; fi
