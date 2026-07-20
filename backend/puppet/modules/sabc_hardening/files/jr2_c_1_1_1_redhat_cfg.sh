#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop autofs.service 2>/dev/null || true
systemctl mask autofs.service 2>/dev/null || true
dnf remove -y autofs
