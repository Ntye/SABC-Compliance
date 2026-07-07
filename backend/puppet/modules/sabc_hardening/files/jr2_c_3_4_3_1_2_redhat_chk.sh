#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 101
rpm -q nftables >/dev/null 2>&1 && exit 1
exit 0
