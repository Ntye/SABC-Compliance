#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop cups.socket cups.service 2>/dev/null || true
systemctl mask cups.socket cups.service 2>/dev/null || true
dnf remove -y cups
