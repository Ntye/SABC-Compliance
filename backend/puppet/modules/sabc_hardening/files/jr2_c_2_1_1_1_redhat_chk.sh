#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
n=0
systemctl is-enabled chronyd.service 2>/dev/null | grep -q enabled && n=$((n+1))
systemctl is-enabled ntpd.service 2>/dev/null | grep -q enabled && n=$((n+1))
systemctl is-enabled systemd-timesyncd.service 2>/dev/null | grep -q enabled && n=$((n+1))
[ "$n" -eq 1 ]
