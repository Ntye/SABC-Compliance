#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl list-unit-files 2>/dev/null | grep -q '^rsync\.service' || exit 0
systemctl stop rsync >/dev/null 2>&1
systemctl mask rsync >/dev/null 2>&1
exit 0
