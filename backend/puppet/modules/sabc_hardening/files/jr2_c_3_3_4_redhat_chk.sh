#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ "$(sysctl -n net.ipv4.conf.all.log_martians 2>/dev/null)" = "1" ] || exit 1
[ "$(sysctl -n net.ipv4.conf.default.log_martians 2>/dev/null)" = "1" ] || exit 1
exit 0
