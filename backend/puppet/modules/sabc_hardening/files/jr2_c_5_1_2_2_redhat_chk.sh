#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q rsyslog >/dev/null 2>&1 || exit 101
systemctl is-enabled rsyslog.service 2>/dev/null | grep -q enabled || exit 1
systemctl is-active rsyslog.service 2>/dev/null | grep -q '^active' || exit 1
exit 0
