#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop smb.service 2>/dev/null || true
systemctl mask smb.service 2>/dev/null || true
dnf remove -y samba
