#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop slapd.service 2>/dev/null || true
systemctl mask slapd.service 2>/dev/null || true
dnf remove -y openldap-servers
