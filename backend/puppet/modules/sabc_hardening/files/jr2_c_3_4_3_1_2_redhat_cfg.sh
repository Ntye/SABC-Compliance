#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
systemctl stop nftables.service 2>/dev/null || true
systemctl mask nftables.service 2>/dev/null || true
exit 0
