#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'install hfs /bin/false\nblacklist hfs\n' > /etc/modprobe.d/hfs.conf
modprobe -r hfs 2>/dev/null || true
exit 0
