#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q rsyslog >/dev/null 2>&1 || exit 0
systemctl unmask rsyslog.service 2>/dev/null || true
systemctl enable --now rsyslog.service
