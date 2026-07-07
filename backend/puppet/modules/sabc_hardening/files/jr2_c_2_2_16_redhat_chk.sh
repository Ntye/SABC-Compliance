#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q rsync-daemon >/dev/null 2>&1 || rpm -q rsync >/dev/null 2>&1 || exit 0
systemctl list-unit-files 2>/dev/null | grep -q '^rsyncd\.service' || exit 0
[ "$(systemctl is-enabled rsyncd 2>/dev/null)" = "masked" ] && exit 0
exit 1
