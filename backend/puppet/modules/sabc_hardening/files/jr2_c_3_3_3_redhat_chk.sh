#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ "$(sysctl -n net.ipv4.conf.all.secure_redirects 2>/dev/null)" = "0" ] || exit 1
[ "$(sysctl -n net.ipv4.conf.default.secure_redirects 2>/dev/null)" = "0" ] || exit 1
exit 0
