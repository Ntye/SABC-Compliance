#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
# N/A when /tmp is not a separate mount point on this node.
findmnt -kn /tmp >/dev/null 2>&1 || exit 101
findmnt -kn /tmp | grep -qw nodev
