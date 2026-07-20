#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
ls /sys/class/net/*/wireless >/dev/null 2>&1 || exit 0
for w in /sys/class/net/*/wireless; do
  i=$(basename "$(dirname "$w")")
  ip link set "$i" down 2>/dev/null || true
  d=$(basename "$(readlink -f "/sys/class/net/$i/device/driver/module")" 2>/dev/null)
  [ -n "$d" ] && printf 'install %s /bin/false\n' "$d" > "/etc/modprobe.d/60-criclo-$d.conf"
done
exit 0
