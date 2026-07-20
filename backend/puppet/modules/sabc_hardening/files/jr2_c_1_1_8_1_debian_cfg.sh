#!/bin/bash
shopt -s globstar 2>/dev/null || true
findmnt -kn /dev/shm >/dev/null 2>&1 || exit 0
if grep -Eq '^[[:space:]]*tmpfs[[:space:]]+/dev/shm[[:space:]]' /etc/fstab; then
  sed -ri 's|^([[:space:]]*tmpfs[[:space:]]+/dev/shm[[:space:]]+tmpfs[[:space:]]+)[^[:space:]]+|\1defaults,rw,nosuid,nodev,noexec,relatime|' /etc/fstab
else
  printf 'tmpfs /dev/shm tmpfs defaults,rw,nosuid,nodev,noexec,relatime 0 0\n' >> /etc/fstab
fi
mount -o remount /dev/shm 2>/dev/null || true
exit 0
