#!/bin/bash
shopt -s globstar 2>/dev/null || true
bad=0
for f in /etc/ssh/ssh_host_*_key; do
  [ -e "$f" ] || continue
  [ "$(stat -c '%U:%G' "$f")" = "root:root" ] || bad=1
  case "$(stat -c '%a' "$f")" in
    600|400|0) : ;;
    *) bad=1 ;;
  esac
done
exit $bad
