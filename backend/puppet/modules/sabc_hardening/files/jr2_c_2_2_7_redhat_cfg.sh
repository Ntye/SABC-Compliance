#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop vsftpd.service 2>/dev/null || true
systemctl mask vsftpd.service 2>/dev/null || true
dnf remove -y vsftpd
