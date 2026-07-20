#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf '0 5 * * * root /usr/sbin/aide --check\n' > /etc/cron.d/aide-check
chmod 600 /etc/cron.d/aide-check
