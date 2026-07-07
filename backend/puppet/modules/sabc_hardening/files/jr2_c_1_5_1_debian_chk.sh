#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W apparmor >/dev/null 2>&1 || exit 1
dpkg-query -W apparmor-utils >/dev/null 2>&1 || exit 1
exit 0
