#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
dnf install -y chrony
systemctl stop ntpd.service systemd-timesyncd.service 2>/dev/null || true
systemctl mask ntpd.service systemd-timesyncd.service 2>/dev/null || true
systemctl unmask chronyd.service 2>/dev/null || true
systemctl enable --now chronyd.service
