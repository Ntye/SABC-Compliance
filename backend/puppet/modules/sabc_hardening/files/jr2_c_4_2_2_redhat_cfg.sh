#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
for f in /etc/ssh/ssh_host_*_key; do
  [ -e "$f" ] || continue
  if getent group ssh_keys >/dev/null 2>&1; then
    chown root:ssh_keys "$f"; chmod 640 "$f"
  else
    chown root:root "$f"; chmod 600 "$f"
  fi
done
exit 0
