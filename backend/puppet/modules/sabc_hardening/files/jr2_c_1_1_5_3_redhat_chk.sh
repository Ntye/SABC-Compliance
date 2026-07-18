#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
# N/A when /var/log is not a separate mount point on this node.
findmnt -kn /var/log >/dev/null 2>&1 || exit 101
findmnt -kn /var/log | grep -qw nosuid
