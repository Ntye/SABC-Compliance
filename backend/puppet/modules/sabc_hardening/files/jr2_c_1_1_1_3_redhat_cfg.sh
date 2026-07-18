#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'install jffs2 /bin/false\nblacklist jffs2\n' > /etc/modprobe.d/jffs2.conf
modprobe -r jffs2 2>/dev/null || true
exit 0
