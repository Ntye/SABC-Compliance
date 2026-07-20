#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'install cramfs /bin/false\nblacklist cramfs\n' > /etc/modprobe.d/cramfs.conf
modprobe -r cramfs 2>/dev/null || true
exit 0
