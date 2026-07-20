#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
nft list ruleset | grep -q 'hook input' || exit 1
nft list ruleset | grep -Eq 'iif "lo" accept' || nft add rule inet filter input iif lo accept
nft list ruleset | grep -Eq 'ip saddr 127\.0\.0\.0/8' || nft add rule inet filter input ip saddr 127.0.0.0/8 counter drop
exit 0
