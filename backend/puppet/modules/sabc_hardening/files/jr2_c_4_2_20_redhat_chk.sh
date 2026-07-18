#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
command -v sshd >/dev/null 2>&1 || exit 101
T=$(sshd -T 2>/dev/null) || exit 1
i=$(echo "$T" | awk '$1=="clientaliveinterval"{print $2}')
c=$(echo "$T" | awk '$1=="clientalivecountmax"{print $2}')
[ -n "$i" ] && [ -n "$c" ] && [ "$i" -ge 1 ] && [ "$c" -ge 1 ]
