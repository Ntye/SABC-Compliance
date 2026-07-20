#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
findmnt -kn /home >/dev/null 2>&1 || exit 0
if grep -Eq '^[^#]+\s\/home\s' /etc/fstab; then
  grep -E '^[^#]+\s\/home\s' /etc/fstab | grep -qw nosuid || \
    sed -ri 's|^([^#]+\s\/home\s+\S+\s+)([^[:space:]]+)|\1\2,nosuid|' /etc/fstab
fi
mount -o remount,nosuid /home 2>/dev/null || mount -o remount /home
