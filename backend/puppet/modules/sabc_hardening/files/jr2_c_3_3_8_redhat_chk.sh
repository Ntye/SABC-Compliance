#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ "$(sysctl -n net.ipv4.tcp_syncookies 2>/dev/null)" = "1" ] || exit 1
exit 0
