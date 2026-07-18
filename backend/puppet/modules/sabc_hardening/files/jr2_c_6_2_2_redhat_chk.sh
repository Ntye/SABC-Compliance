#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
awk -F: '($2 == "") {print $1}' /etc/shadow | grep -q . && exit 1
exit 0
