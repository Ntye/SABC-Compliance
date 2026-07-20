#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
nft list ruleset > /etc/nftables/criclo.nft
grep -q '/etc/nftables/criclo.nft' /etc/sysconfig/nftables.conf 2>/dev/null || \
  printf 'include "/etc/nftables/criclo.nft"\n' >> /etc/sysconfig/nftables.conf
exit 0
