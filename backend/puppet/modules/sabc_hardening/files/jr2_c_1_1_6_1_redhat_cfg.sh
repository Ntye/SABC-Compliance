#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
findmnt -kn /var/log/audit >/dev/null 2>&1 || exit 0
if grep -Eq '^[^#]+\s\/var\/log\/audit\s' /etc/fstab; then
  grep -E '^[^#]+\s\/var\/log\/audit\s' /etc/fstab | grep -qw nodev || \
    sed -ri 's|^([^#]+\s\/var\/log\/audit\s+\S+\s+)([^[:space:]]+)|\1\2,nodev|' /etc/fstab
fi
mount -o remount,nodev /var/log/audit 2>/dev/null || mount -o remount /var/log/audit
