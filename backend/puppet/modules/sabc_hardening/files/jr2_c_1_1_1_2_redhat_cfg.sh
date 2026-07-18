#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'install freevxfs /bin/false\nblacklist freevxfs\n' > /etc/modprobe.d/freevxfs.conf
modprobe -r freevxfs 2>/dev/null || true
exit 0
