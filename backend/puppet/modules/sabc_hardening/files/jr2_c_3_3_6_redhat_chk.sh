#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ "$(sysctl -n net.ipv4.icmp_ignore_bogus_error_responses 2>/dev/null)" = "1" ] || exit 1
exit 0
