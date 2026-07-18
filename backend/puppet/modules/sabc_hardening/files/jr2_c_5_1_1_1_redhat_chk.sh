#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl is-active systemd-journald.service 2>/dev/null | grep -q '^active'
