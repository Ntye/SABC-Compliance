#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
v=$(awk '/^\s*PASS_MAX_DAYS\b/ {print $2}' /etc/login.defs)
[ -n "$v" ] || exit 1
[ "$v" -ge 1 ] && [ "$v" -le 365 ] || exit 1
bad=$(awk -F: '($2!~/^[!*]/ && ($5>365 || $5 == "" || $5 == -1)) {print $1}' /etc/shadow)
[ -z "$bad" ]
