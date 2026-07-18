#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q at >/dev/null 2>&1 || exit 0
touch /etc/at.allow
chown root:root /etc/at.allow
chmod 640 /etc/at.allow
if [ -f /etc/at.deny ]; then chown root:root /etc/at.deny; chmod 640 /etc/at.deny; fi
exit 0
