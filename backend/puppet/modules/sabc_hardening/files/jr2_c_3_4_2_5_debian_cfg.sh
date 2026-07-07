#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
dpkg-query -W nftables >/dev/null 2>&1 || exit 0
nft list chain inet filter input >/dev/null 2>&1 || exit 0
nft list chain inet filter input | grep -q 'iif "lo" accept' || nft add rule inet filter input iif lo accept
nft list chain inet filter input | grep -Eq 'ip saddr 127\.0\.0\.0/8.*drop' || nft add rule inet filter input ip saddr 127.0.0.0/8 counter drop
exit 0
