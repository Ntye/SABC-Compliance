#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 0
[ -f /etc/gdm/custom.conf ] || exit 0
sed -ri '/^\[xdmcp\]/,/^\[/ s/^\s*Enable\s*=\s*true/#Enable=false/' /etc/gdm/custom.conf
