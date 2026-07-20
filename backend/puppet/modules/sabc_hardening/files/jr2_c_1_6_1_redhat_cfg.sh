#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'Authorized users only. All activity may be monitored and reported.\n' > /etc/motd
chown root:root /etc/motd
chmod u-x,go-wx /etc/motd
