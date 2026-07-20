#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
for f in /etc/ssh/ssh_host_*_key.pub; do
  [ -e "$f" ] || continue
  chown root:root "$f"
  chmod 644 "$f"
done
exit 0
