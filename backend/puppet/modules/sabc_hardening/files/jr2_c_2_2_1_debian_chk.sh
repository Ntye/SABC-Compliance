#!/usr/bin/env bash
# Package-state guard (generated): exit 0 = compliant.
pkg_installed() {
  if command -v rpm >/dev/null 2>&1 && rpm -q "$1" >/dev/null 2>&1; then return 0; fi
  if command -v dpkg-query >/dev/null 2>&1 \
     && [ "$(dpkg-query -W -f='${db:Status-Status}' "$1" 2>/dev/null)" = installed ]; then return 0; fi
  return 1
}
for p in avahi-daemon; do
  if pkg_installed "$p"; then exit 1; fi
done
exit 0
