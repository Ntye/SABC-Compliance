#!/bin/bash
shopt -s globstar 2>/dev/null || true
for f in /etc/security/opasswd /etc/security/opasswd.old; do
  [ -e "$f" ] || continue
  [ "$(stat -c '%a %U %G' "$f")" = "600 root root" ] || exit 1
done
exit 0
