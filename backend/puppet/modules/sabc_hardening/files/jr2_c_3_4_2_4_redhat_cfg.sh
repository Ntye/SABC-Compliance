#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 0
rpm -q nftables >/dev/null 2>&1 || exit 0
nft list table inet filter >/dev/null 2>&1 || nft create table inet filter
nft list chain inet filter input >/dev/null 2>&1 || nft create chain inet filter input '{ type filter hook input priority 0 ; policy accept ; }'
nft list chain inet filter forward >/dev/null 2>&1 || nft create chain inet filter forward '{ type filter hook forward priority 0 ; policy accept ; }'
nft list chain inet filter output >/dev/null 2>&1 || nft create chain inet filter output '{ type filter hook output priority 0 ; policy accept ; }'
exit 0
