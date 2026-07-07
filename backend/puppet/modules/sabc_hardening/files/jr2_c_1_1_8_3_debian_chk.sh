#!/bin/bash
shopt -s globstar 2>/dev/null || true
findmnt -kn /dev/shm >/dev/null 2>&1 || exit 101
findmnt -kn /dev/shm | grep -qw nosuid && exit 0
exit 1
