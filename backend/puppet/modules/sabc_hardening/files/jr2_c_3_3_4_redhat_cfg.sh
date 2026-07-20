#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'net.ipv4.conf.all.log_martians = 1\nnet.ipv4.conf.default.log_martians = 1\n' > /etc/sysctl.d/60-criclo-log-martians.conf
sysctl -w net.ipv4.conf.all.log_martians=1
sysctl -w net.ipv4.conf.default.log_martians=1
sysctl -w net.ipv4.route.flush=1
