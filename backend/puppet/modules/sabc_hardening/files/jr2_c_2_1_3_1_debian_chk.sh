#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-enabled systemd-timesyncd 2>/dev/null | grep -q '^enabled' || exit 101
grep -Ersq '^[[:space:]]*(NTP|FallbackNTP)=[^[:space:]]' /etc/systemd/timesyncd.conf /etc/systemd/timesyncd.conf.d 2>/dev/null && exit 0
exit 1
