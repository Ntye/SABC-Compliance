#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W gdm3 >/dev/null 2>&1 || exit 101
grep -Eqsi '^[[:space:]]*Enable[[:space:]]*=[[:space:]]*true' /etc/gdm3/custom.conf /etc/gdm/custom.conf 2>/dev/null && exit 1
exit 0
