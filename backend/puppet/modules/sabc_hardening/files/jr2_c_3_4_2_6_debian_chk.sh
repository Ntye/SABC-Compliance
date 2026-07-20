#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
dpkg-query -W nftables >/dev/null 2>&1 || exit 101
r=$(nft list ruleset 2>/dev/null) || exit 1
printf '%s' "$r" | grep -q 'hook input' || exit 1
n=$(printf '%s' "$r" | grep -cE 'hook (input|forward|output)')
d=$(printf '%s' "$r" | grep -E 'hook (input|forward|output)' | grep -c 'policy drop')
[ "$n" -gt 0 ] && [ "$n" -eq "$d" ] && exit 0
exit 1
