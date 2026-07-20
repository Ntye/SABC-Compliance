#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
f=/etc/group-
[ -e "$f" ] || exit 0
chown root:root "$f"
chmod 644 "$f"
