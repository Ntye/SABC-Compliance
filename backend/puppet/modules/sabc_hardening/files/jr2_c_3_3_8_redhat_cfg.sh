#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'net.ipv4.tcp_syncookies = 1\n' > /etc/sysctl.d/60-criclo-syncookies.conf
sysctl -w net.ipv4.tcp_syncookies=1
sysctl -w net.ipv4.route.flush=1
