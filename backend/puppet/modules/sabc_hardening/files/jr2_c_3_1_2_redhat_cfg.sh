#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop bluetooth.service 2>/dev/null || true
systemctl mask bluetooth.service 2>/dev/null || true
exit 0
