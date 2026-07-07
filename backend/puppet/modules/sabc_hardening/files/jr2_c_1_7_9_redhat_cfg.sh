#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 0
[ -e /etc/gdm/custom.conf ] && sed -ri 's/^[[:space:]]*Enable[[:space:]]*=[[:space:]]*true/Enable=false/I' /etc/gdm/custom.conf
exit 0
