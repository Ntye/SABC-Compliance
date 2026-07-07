#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
dpkg-query -W nftables >/dev/null 2>&1 || exit 101
grep -Eqs '^[[:space:]]*include[[:space:]]+"/etc/nftables\.d/sabc\.nft"' /etc/nftables.conf && [ -s /etc/nftables.d/sabc.nft ] && exit 0
exit 1
