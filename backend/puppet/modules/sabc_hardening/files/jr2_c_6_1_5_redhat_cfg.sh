#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
f=/etc/shadow
[ -e "$f" ] || exit 0
chown root:root "$f"
chmod 0 "$f"
