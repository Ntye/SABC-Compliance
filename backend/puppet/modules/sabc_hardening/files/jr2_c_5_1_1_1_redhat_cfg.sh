#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl unmask systemd-journald.service 2>/dev/null || true
systemctl start systemd-journald.service
