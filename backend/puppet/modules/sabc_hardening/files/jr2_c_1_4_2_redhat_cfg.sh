#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'kernel.randomize_va_space = 2\n' > /etc/sysctl.d/60-criclo-aslr.conf
sysctl -w kernel.randomize_va_space=2
