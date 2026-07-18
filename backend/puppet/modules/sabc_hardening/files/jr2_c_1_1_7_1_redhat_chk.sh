#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
# N/A when /home is not a separate mount point on this node.
findmnt -kn /home >/dev/null 2>&1 || exit 101
findmnt -kn /home | grep -qw nodev
