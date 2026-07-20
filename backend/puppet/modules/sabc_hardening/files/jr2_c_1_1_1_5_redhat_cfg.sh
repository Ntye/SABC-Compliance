#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'install hfsplus /bin/false\nblacklist hfsplus\n' > /etc/modprobe.d/hfsplus.conf
modprobe -r hfsplus 2>/dev/null || true
exit 0
