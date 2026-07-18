#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl list-unit-files systemd-timesyncd.service 2>/dev/null | grep -q systemd-timesyncd || exit 101
grep -Ersq '^\s*NTP=\S+' /etc/systemd/timesyncd.conf /etc/systemd/timesyncd.conf.d 2>/dev/null
