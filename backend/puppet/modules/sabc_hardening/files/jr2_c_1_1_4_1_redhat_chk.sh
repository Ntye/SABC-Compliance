#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
# N/A when /var/tmp is not a separate mount point on this node.
findmnt -kn /var/tmp >/dev/null 2>&1 || exit 101
findmnt -kn /var/tmp | grep -qw nodev
