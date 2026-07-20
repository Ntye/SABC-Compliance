#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop squid.service 2>/dev/null || true
systemctl mask squid.service 2>/dev/null || true
dnf remove -y squid
