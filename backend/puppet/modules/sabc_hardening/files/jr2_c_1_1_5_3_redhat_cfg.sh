#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
findmnt -kn /var/log >/dev/null 2>&1 || exit 0
if grep -Eq '^[^#]+\s\/var\/log\s' /etc/fstab; then
  grep -E '^[^#]+\s\/var\/log\s' /etc/fstab | grep -qw nosuid || \
    sed -ri 's|^([^#]+\s\/var\/log\s+\S+\s+)([^[:space:]]+)|\1\2,nosuid|' /etc/fstab
fi
mount -o remount,nosuid /var/log 2>/dev/null || mount -o remount /var/log
