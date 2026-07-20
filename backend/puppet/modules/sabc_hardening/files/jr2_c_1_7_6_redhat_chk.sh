#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 101
grep -Ersq '^\s*automount(-open)?\s*=\s*false' /etc/dconf/db/*.d 2>/dev/null || exit 1
grep -Ersq '/org/gnome/desktop/media-handling/automount' /etc/dconf/db/*.d/locks 2>/dev/null || exit 1
exit 0
