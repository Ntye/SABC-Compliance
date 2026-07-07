#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 101
dpkg-query -W nftables >/dev/null 2>&1 && exit 1
exit 0
