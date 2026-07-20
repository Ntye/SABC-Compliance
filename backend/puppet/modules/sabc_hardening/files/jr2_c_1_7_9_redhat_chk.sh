#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 101
[ -f /etc/gdm/custom.conf ] || exit 0
awk '/^\[xdmcp\]/{f=1;next} /^\[/{f=0} f && /^\s*Enable\s*=\s*true/{found=1} END{exit found?1:0}' /etc/gdm/custom.conf
