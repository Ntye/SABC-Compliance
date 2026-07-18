#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q postfix >/dev/null 2>&1 || exit 0
postconf -e 'inet_interfaces = loopback-only'
systemctl try-restart postfix.service 2>/dev/null || true
exit 0
