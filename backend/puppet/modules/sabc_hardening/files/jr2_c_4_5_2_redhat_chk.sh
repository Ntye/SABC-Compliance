#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
u=$(awk '/^\s*UMASK\s/ {print $2}' /etc/login.defs | tail -n1)
case "$u" in 027|077) : ;; *) exit 1 ;; esac
grep -Ersq '^\s*umask\s+0?(0[0-2][0-7]|[0-2][0-7])\b' /etc/profile /etc/profile.d /etc/bashrc 2>/dev/null && exit 1
exit 0
