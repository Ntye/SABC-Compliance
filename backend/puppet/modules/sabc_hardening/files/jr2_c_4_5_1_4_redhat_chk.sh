#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
d=$(useradd -D | awk -F= '/INACTIVE/{print $2}')
[ -n "$d" ] && [ "$d" -ge 0 ] && [ "$d" -le 30 ] || exit 1
bad=$(awk -F: '($2!~/^[!*]/ && ($7 == "" || $7 > 30 || $7 < 0)) {print $1}' /etc/shadow)
[ -z "$bad" ]
