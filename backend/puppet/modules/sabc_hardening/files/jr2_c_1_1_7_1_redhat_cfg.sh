#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
findmnt -kn /home >/dev/null 2>&1 || exit 0
if grep -Eq '^[^#]+\s\/home\s' /etc/fstab; then
  grep -E '^[^#]+\s\/home\s' /etc/fstab | grep -qw nodev || \
    sed -ri 's|^([^#]+\s\/home\s+\S+\s+)([^[:space:]]+)|\1\2,nodev|' /etc/fstab
fi
mount -o remount,nodev /home 2>/dev/null || mount -o remount /home
