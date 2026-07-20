#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
[ "$(sysctl -n kernel.randomize_va_space 2>/dev/null)" = "2" ] || exit 1
exit 0
