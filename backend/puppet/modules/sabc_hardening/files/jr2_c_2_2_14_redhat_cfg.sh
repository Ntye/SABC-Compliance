#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop dnsmasq.service 2>/dev/null || true
systemctl mask dnsmasq.service 2>/dev/null || true
dnf remove -y dnsmasq
