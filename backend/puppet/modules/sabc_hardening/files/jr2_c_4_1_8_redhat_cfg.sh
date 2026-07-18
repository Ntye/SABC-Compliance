#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
touch /etc/cron.allow
chown root:root /etc/cron.allow
chmod 640 /etc/cron.allow
if [ -f /etc/cron.deny ]; then chown root:root /etc/cron.deny; chmod 640 /etc/cron.deny; fi
exit 0
