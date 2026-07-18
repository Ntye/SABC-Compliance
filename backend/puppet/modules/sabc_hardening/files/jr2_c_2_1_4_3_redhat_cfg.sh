#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q ntp >/dev/null 2>&1 || exit 0
systemctl unmask ntpd.service 2>/dev/null || true
systemctl enable --now ntpd.service
