#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 0
rpm -q nftables >/dev/null 2>&1 || exit 0
mkdir -p /etc/nftables
nft list ruleset > /etc/nftables/sabc.nft 2>/dev/null || exit 0
grep -Eqs '^[[:space:]]*include[[:space:]]+"/etc/nftables/sabc\.nft"' /etc/sysconfig/nftables.conf || printf 'include "/etc/nftables/sabc.nft"\n' >> /etc/sysconfig/nftables.conf
systemctl enable nftables >/dev/null 2>&1
exit 0
