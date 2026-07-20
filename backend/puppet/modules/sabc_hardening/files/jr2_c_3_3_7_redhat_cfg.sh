#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'net.ipv4.conf.all.rp_filter = 1\nnet.ipv4.conf.default.rp_filter = 1\n' > /etc/sysctl.d/60-criclo-rp-filter.conf
sysctl -w net.ipv4.conf.all.rp_filter=1
sysctl -w net.ipv4.conf.default.rp_filter=1
sysctl -w net.ipv4.route.flush=1
