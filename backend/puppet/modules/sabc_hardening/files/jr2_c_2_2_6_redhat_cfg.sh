#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop named.service 2>/dev/null || true
systemctl mask named.service 2>/dev/null || true
dnf remove -y bind
