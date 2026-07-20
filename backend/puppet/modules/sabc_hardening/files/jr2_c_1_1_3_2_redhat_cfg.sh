#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
findmnt -kn /var >/dev/null 2>&1 || exit 0
if grep -Eq '^[^#]+\s\/var\s' /etc/fstab; then
  grep -E '^[^#]+\s\/var\s' /etc/fstab | grep -qw nosuid || \
    sed -ri 's|^([^#]+\s\/var\s+\S+\s+)([^[:space:]]+)|\1\2,nosuid|' /etc/fstab
fi
mount -o remount,nosuid /var 2>/dev/null || mount -o remount /var
