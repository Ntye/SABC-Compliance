#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
ls /sys/class/net/*/wireless >/dev/null 2>&1 || exit 101
for w in /sys/class/net/*/wireless; do
  i=$(basename "$(dirname "$w")")
  ip link show "$i" 2>/dev/null | grep -q 'state UP' && exit 1
done
exit 0
