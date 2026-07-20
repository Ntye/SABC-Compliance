#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q chrony >/dev/null 2>&1 || exit 101
systemctl is-enabled chronyd.service 2>/dev/null | grep -q enabled || exit 1
systemctl is-active chronyd.service 2>/dev/null | grep -q '^active' || exit 1
exit 0
