#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W rsync >/dev/null 2>&1 || exit 0
systemctl list-unit-files 2>/dev/null | grep -q '^rsync\.service' || exit 0
[ "$(systemctl is-enabled rsync 2>/dev/null)" = "masked" ] && exit 0
exit 1
