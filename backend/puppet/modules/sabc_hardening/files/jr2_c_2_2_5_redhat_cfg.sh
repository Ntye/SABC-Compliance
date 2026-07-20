#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop nfs-server.service 2>/dev/null || true
systemctl mask nfs-server.service 2>/dev/null || true
dnf remove -y nfs-utils
