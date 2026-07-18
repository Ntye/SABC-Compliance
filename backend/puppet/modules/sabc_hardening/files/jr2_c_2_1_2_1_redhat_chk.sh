#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q chrony >/dev/null 2>&1 || exit 101
pgrep -u root -x chronyd >/dev/null 2>&1 && exit 1
exit 0
