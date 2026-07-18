#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
awk -F: '($2 != "x") {print $1}' /etc/passwd | grep -q . && exit 1
exit 0
