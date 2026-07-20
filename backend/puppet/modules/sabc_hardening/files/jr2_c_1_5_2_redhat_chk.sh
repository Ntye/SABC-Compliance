#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
command -v grubby >/dev/null 2>&1 || exit 101
grubby --info=ALL 2>/dev/null | grep -Eq '(selinux=0|enforcing=0)' && exit 1
exit 0
