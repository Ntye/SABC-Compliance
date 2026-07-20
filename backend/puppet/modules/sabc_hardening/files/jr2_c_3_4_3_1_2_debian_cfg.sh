#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 0
dpkg-query -W nftables >/dev/null 2>&1 || exit 0
DEBIAN_FRONTEND=noninteractive apt-get -y purge nftables >/dev/null
exit 0
