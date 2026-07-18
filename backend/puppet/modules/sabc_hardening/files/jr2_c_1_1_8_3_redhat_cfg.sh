#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
findmnt -kn /dev/shm >/dev/null 2>&1 || exit 0
if grep -Eq '^[^#]+\s\/dev\/shm\s' /etc/fstab; then
  grep -E '^[^#]+\s\/dev\/shm\s' /etc/fstab | grep -qw nosuid || \
    sed -ri 's|^([^#]+\s\/dev\/shm\s+\S+\s+)([^[:space:]]+)|\1\2,nosuid|' /etc/fstab
fi
mount -o remount,nosuid /dev/shm 2>/dev/null || mount -o remount /dev/shm
