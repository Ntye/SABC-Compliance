#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
findmnt -kn /tmp >/dev/null 2>&1 || exit 0
if grep -Eq '^[^#]+\s\/tmp\s' /etc/fstab; then
  grep -E '^[^#]+\s\/tmp\s' /etc/fstab | grep -qw nosuid || \
    sed -ri 's|^([^#]+\s\/tmp\s+\S+\s+)([^[:space:]]+)|\1\2,nosuid|' /etc/fstab
fi
mount -o remount,nosuid /tmp 2>/dev/null || mount -o remount /tmp
