#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
command -v sshd >/dev/null 2>&1 || exit 101
T=$(sshd -T 2>/dev/null) || exit 1
v=$(echo "$T" | awk '$1=="maxsessions"{print $2}')
[ -n "$v" ] && [ "$v" -le 10 ]
