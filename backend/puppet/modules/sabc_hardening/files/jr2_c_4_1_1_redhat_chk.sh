#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q cronie >/dev/null 2>&1 || exit 101
systemctl is-enabled crond.service 2>/dev/null | grep -q enabled || exit 1
systemctl is-active crond.service 2>/dev/null | grep -q '^active' || exit 1
exit 0
