#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 101
grep -Ersq '^\s*idle-delay\s*=\s*uint32\s+[1-9]' /etc/dconf/db/*.d 2>/dev/null || exit 1
exit 0
