#!/bin/bash
shopt -s globstar 2>/dev/null || true
for f in /etc/ssh/ssh_host_*_key; do
  [ -e "$f" ] || continue
  chown root:root "$f"
  chmod 0600 "$f"
done
exit 0
