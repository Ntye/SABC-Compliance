#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'net.ipv4.conf.all.send_redirects = 0\nnet.ipv4.conf.default.send_redirects = 0\n' > /etc/sysctl.d/60-criclo-send-redirects.conf
sysctl -w net.ipv4.conf.all.send_redirects=0
sysctl -w net.ipv4.conf.default.send_redirects=0
sysctl -w net.ipv4.route.flush=1
