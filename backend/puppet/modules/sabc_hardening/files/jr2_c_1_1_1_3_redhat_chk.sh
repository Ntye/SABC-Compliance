#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
# Compliant when the jffs2 kernel module cannot be loaded and is not loaded.
lsmod | grep -q '^jffs2\b' && exit 1
out=$(modprobe -n -v jffs2 2>/dev/null)
[ -z "$out" ] && exit 0                     # not available in this kernel
echo "$out" | grep -Eq '(^|/bin/)(true|false)' && exit 0
exit 1
