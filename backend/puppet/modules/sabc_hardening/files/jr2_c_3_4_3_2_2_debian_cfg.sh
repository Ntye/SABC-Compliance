#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 0
command -v iptables >/dev/null 2>&1 || exit 0
iptables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || iptables -A INPUT -i lo -j ACCEPT
iptables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || iptables -A OUTPUT -o lo -j ACCEPT
iptables -C INPUT -s 127.0.0.0/8 -j DROP >/dev/null 2>&1 || iptables -A INPUT -s 127.0.0.0/8 -j DROP
exit 0
