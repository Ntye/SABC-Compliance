#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
for k in net.ipv4.conf.all.accept_source_route net.ipv4.conf.default.accept_source_route; do
  [ "$(sysctl -n $k 2>/dev/null)" = "0" ] || exit 1
done
for k in net.ipv6.conf.all.accept_source_route net.ipv6.conf.default.accept_source_route; do
  v=$(sysctl -n $k 2>/dev/null); [ -z "$v" ] || [ "$v" = "0" ] || exit 1
done
exit 0
