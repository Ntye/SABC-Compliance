#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
command -v grubby >/dev/null 2>&1 || exit 0
grubby --update-kernel ALL --remove-args 'selinux=0 enforcing=0'
