#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
systemctl is-enabled nftables.service 2>/dev/null | grep -q enabled && exit 0
dnf install -y iptables iptables-services
