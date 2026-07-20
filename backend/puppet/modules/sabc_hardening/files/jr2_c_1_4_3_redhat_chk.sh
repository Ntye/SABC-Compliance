#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
v=$(sysctl -n kernel.yama.ptrace_scope 2>/dev/null)
[ -n "$v" ] && [ "$v" -ge 1 ] && [ "$v" -le 3 ]
