#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
# N/A when another firewall (firewalld) is the active choice on this node.
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 101
systemctl is-enabled nftables.service 2>/dev/null | grep -q enabled && exit 101
rpm -q iptables iptables-services >/dev/null 2>&1
