#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl is-enabled firewalld 2>/dev/null | grep -q enabled || exit 1
systemctl is-active --quiet firewalld || exit 1
exit 0
