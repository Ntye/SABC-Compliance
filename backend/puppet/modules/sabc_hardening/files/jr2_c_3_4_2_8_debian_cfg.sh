#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
dpkg-query -W nftables >/dev/null 2>&1 || exit 0
mkdir -p /etc/nftables.d
nft list ruleset > /etc/nftables.d/sabc.nft 2>/dev/null || exit 0
grep -Eqs '^[[:space:]]*include[[:space:]]+"/etc/nftables\.d/sabc\.nft"' /etc/nftables.conf || printf 'include "/etc/nftables.d/sabc.nft"\n' >> /etc/nftables.conf
systemctl enable nftables >/dev/null 2>&1
exit 0
