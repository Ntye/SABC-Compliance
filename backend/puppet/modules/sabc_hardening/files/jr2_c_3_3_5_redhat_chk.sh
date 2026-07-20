#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ "$(sysctl -n net.ipv4.icmp_echo_ignore_broadcasts 2>/dev/null)" = "1" ] || exit 1
exit 0
