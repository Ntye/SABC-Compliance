#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
rpm -q nftables >/dev/null 2>&1 || exit 101
grep -Eqs '^[[:space:]]*include[[:space:]]+"/etc/nftables/sabc\.nft"' /etc/sysconfig/nftables.conf && [ -s /etc/nftables/sabc.nft ] && exit 0
exit 1
