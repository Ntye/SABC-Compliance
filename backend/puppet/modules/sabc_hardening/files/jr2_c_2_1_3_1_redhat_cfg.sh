#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl list-unit-files systemd-timesyncd.service 2>/dev/null | grep -q systemd-timesyncd || exit 0
mkdir -p /etc/systemd/timesyncd.conf.d
printf '[Time]\nNTP=pool.ntp.org\n' > /etc/systemd/timesyncd.conf.d/60-criclo.conf
systemctl try-restart systemd-timesyncd.service 2>/dev/null || true
exit 0
