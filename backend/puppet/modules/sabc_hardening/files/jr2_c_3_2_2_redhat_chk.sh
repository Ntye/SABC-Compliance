#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ "$(sysctl -n net.ipv4.ip_forward 2>/dev/null)" = "0" ] || exit 1
v6=$(sysctl -n net.ipv6.conf.all.forwarding 2>/dev/null)
[ -z "$v6" ] || [ "$v6" = "0" ] || exit 1
exit 0
