#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
installed=0
for p in rpcbind; do rpm -q "$p" >/dev/null 2>&1 && installed=1; done
[ "$installed" -eq 0 ] && exit 0
# Package present (may be a dependency): its units must be neither enabled nor active.
systemctl is-enabled rpcbind.socket rpcbind.service 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active rpcbind.socket rpcbind.service 2>/dev/null | grep -q '^active' && exit 1
exit 0
