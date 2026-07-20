#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ -e /etc/crontab ] || exit 0
chown root:root /etc/crontab
if [ -d /etc/crontab ]; then chmod og-rwx /etc/crontab; else chmod og-rwx,u-x /etc/crontab; fi
