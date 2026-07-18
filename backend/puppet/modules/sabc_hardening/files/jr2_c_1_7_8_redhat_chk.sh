#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 101
grep -Ersq '^\s*autorun-never\s*=\s*true' /etc/dconf/db/*.d 2>/dev/null || exit 1
grep -Ersq '/org/gnome/desktop/media-handling/autorun-never' /etc/dconf/db/*.d/locks 2>/dev/null || exit 1
exit 0
