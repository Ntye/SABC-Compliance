#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'Authorized users only. All activity may be monitored and reported.\n' > /etc/issue
chown root:root /etc/issue
chmod u-x,go-wx /etc/issue
