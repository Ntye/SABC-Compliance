#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'net.ipv4.conf.all.accept_redirects = 0\nnet.ipv4.conf.default.accept_redirects = 0\nnet.ipv6.conf.all.accept_redirects = 0\nnet.ipv6.conf.default.accept_redirects = 0\n' > /etc/sysctl.d/60-criclo-accept-redirects.conf
sysctl -w net.ipv4.conf.all.accept_redirects=0
sysctl -w net.ipv4.conf.default.accept_redirects=0
sysctl -w net.ipv6.conf.all.accept_redirects=0 2>/dev/null || true
sysctl -w net.ipv6.conf.default.accept_redirects=0 2>/dev/null || true
sysctl -w net.ipv4.route.flush=1
exit 0
