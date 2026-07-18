#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'net.ipv4.icmp_ignore_bogus_error_responses = 1\n' > /etc/sysctl.d/60-criclo-icmp-bogus.conf
sysctl -w net.ipv4.icmp_ignore_bogus_error_responses=1
sysctl -w net.ipv4.route.flush=1
