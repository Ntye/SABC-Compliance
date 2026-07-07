#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl list-unit-files 2>/dev/null | grep -q '^bluetooth\.service' || exit 0
systemctl stop bluetooth >/dev/null 2>&1
systemctl mask bluetooth >/dev/null 2>&1
exit 0
