#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ "$(sysctl -n net.ipv4.conf.all.rp_filter 2>/dev/null)" = "1" ] || exit 1
[ "$(sysctl -n net.ipv4.conf.default.rp_filter 2>/dev/null)" = "1" ] || exit 1
exit 0
