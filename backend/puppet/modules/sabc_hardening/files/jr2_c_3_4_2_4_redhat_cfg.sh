#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
nft list tables 2>/dev/null | grep -q 'inet filter' || nft create table inet filter
nft list ruleset | grep -q 'hook input'   || nft create chain inet filter input   '{ type filter hook input priority 0 ; }'
nft list ruleset | grep -q 'hook forward' || nft create chain inet filter forward '{ type filter hook forward priority 0 ; }'
nft list ruleset | grep -q 'hook output'  || nft create chain inet filter output  '{ type filter hook output priority 0 ; }'
exit 0
