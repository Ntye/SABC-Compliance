#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
rpm -q nftables >/dev/null 2>&1 || exit 101
r=$(nft list ruleset 2>/dev/null) || exit 1
printf '%s' "$r" | grep -q 'hook input' || exit 1
printf '%s' "$r" | grep -q 'hook forward' || exit 1
printf '%s' "$r" | grep -q 'hook output' || exit 1
exit 0
