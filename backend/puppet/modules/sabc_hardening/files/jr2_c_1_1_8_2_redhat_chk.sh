#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
# N/A when /dev/shm is not a separate mount point on this node.
findmnt -kn /dev/shm >/dev/null 2>&1 || exit 101
findmnt -kn /dev/shm | grep -qw noexec
