#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ -e /etc/cron.daily ] || exit 0
chown root:root /etc/cron.daily
if [ -d /etc/cron.daily ]; then chmod og-rwx /etc/cron.daily; else chmod og-rwx,u-x /etc/cron.daily; fi
