#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 0
command -v ip6tables >/dev/null 2>&1 || exit 0
ip6tables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || ip6tables -A INPUT -i lo -j ACCEPT
ip6tables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || ip6tables -A OUTPUT -o lo -j ACCEPT
ip6tables -C INPUT -s ::1 -j DROP >/dev/null 2>&1 || ip6tables -A INPUT -s ::1 -j DROP
exit 0
