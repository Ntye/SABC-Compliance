#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
find / -xdev \( -path /proc -o -path /sys -o -path /run -o -path /tmp -o -path /var/tmp -o -path /dev/shm \) -prune \
  -o -type f -perm -0002 -exec chmod o-w {} + 2>/dev/null
find / -xdev \( -path /proc -o -path /sys -o -path /run \) -prune \
  -o -type d -perm -0002 ! -perm -1000 -exec chmod a+t {} + 2>/dev/null
exit 0
