#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 101
command -v iptables >/dev/null 2>&1 || exit 1
iptables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || exit 1
iptables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || exit 1
iptables -C INPUT -s 127.0.0.0/8 -j DROP >/dev/null 2>&1 || exit 1
exit 0
