#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl list-unit-files 2>/dev/null | grep -q '^rsyncd\.service' || exit 0
systemctl stop rsyncd >/dev/null 2>&1
systemctl mask rsyncd >/dev/null 2>&1
exit 0
