#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop dhcpd.service dhcpd6.service 2>/dev/null || true
systemctl mask dhcpd.service dhcpd6.service 2>/dev/null || true
dnf remove -y dhcp-server
