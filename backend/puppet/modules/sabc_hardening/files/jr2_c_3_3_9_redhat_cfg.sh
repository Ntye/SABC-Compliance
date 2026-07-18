#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
sysctl -n net.ipv6.conf.all.accept_ra >/dev/null 2>&1 || exit 0
printf 'net.ipv6.conf.all.accept_ra = 0\nnet.ipv6.conf.default.accept_ra = 0\n' > /etc/sysctl.d/60-criclo-accept-ra.conf
sysctl -w net.ipv6.conf.all.accept_ra=0
sysctl -w net.ipv6.conf.default.accept_ra=0
sysctl -w net.ipv4.route.flush=1
sysctl -w net.ipv6.route.flush=1 2>/dev/null || true
