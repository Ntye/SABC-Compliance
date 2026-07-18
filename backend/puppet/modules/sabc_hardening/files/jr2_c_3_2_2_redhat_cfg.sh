#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'net.ipv4.ip_forward = 0\nnet.ipv6.conf.all.forwarding = 0\n' > /etc/sysctl.d/60-criclo-forwarding.conf
sysctl -w net.ipv4.ip_forward=0
sysctl -w net.ipv6.conf.all.forwarding=0 2>/dev/null || true
sysctl -w net.ipv4.route.flush=1
exit 0
