#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
# N/A when another firewall (firewalld) is the active choice on this node.
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 101
rpm -q nftables >/dev/null 2>&1 || exit 101
nft list ruleset 2>/dev/null | grep -Eq 'hook input' || exit 1
nft list ruleset 2>/dev/null | grep -Eq 'hook forward' || exit 1
nft list ruleset 2>/dev/null | grep -Eq 'hook output' || exit 1
exit 0
