#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
v=$(awk '/^\s*PASS_WARN_AGE\b/ {print $2}' /etc/login.defs)
[ -n "$v" ] || exit 1
[ "$v" -ge 7 ] || exit 1
bad=$(awk -F: '($2!~/^[!*]/ && $6<7) {print $1}' /etc/shadow)
[ -z "$bad" ]
