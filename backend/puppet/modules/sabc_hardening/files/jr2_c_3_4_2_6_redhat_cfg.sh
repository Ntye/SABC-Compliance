#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 0
rpm -q nftables >/dev/null 2>&1 || exit 0
nft list chain inet filter input >/dev/null 2>&1 || exit 0
nft list chain inet filter input | grep -q 'iif "lo" accept' || nft add rule inet filter input iif lo accept
nft list chain inet filter input | grep -q 'ct state established,related accept' || nft add rule inet filter input ct state established,related accept
nft list chain inet filter input | grep -q 'tcp dport 22 accept' || nft add rule inet filter input tcp dport 22 accept
nft list chain inet filter output | grep -q 'ct state established,related accept' || nft add rule inet filter output ct state established,related accept
for ch in input forward output; do
  nft chain inet filter "$ch" '{ policy drop ; }'
done
exit 0
