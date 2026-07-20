#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
# N/A when IPv6 is disabled on this node (key absent).
sysctl -n net.ipv6.conf.all.accept_ra >/dev/null 2>&1 || exit 101
[ "$(sysctl -n net.ipv6.conf.all.accept_ra 2>/dev/null)" = "0" ] || exit 1
[ "$(sysctl -n net.ipv6.conf.default.accept_ra 2>/dev/null)" = "0" ] || exit 1
exit 0
