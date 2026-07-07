#!/bin/bash
shopt -s globstar 2>/dev/null || true
for f in /etc/security/opasswd /etc/security/opasswd.old; do
  [ -e "$f" ] || continue
  chown root:root "$f"
  chmod 0600 "$f"
done
exit 0
