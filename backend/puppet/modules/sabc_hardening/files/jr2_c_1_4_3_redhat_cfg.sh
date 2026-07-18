#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'kernel.yama.ptrace_scope = 1\n' > /etc/sysctl.d/60-criclo-ptrace.conf
sysctl -w kernel.yama.ptrace_scope=1
