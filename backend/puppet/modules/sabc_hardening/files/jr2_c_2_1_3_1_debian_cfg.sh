#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-enabled systemd-timesyncd 2>/dev/null | grep -q '^enabled' || exit 0
mkdir -p /etc/systemd/timesyncd.conf.d
printf '[Time]\nNTP=0.pool.ntp.org 1.pool.ntp.org\nFallbackNTP=2.pool.ntp.org 3.pool.ntp.org\n' > /etc/systemd/timesyncd.conf.d/60-sabc.conf
systemctl try-restart systemd-timesyncd >/dev/null 2>&1
exit 0
