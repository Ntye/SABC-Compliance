#!/bin/bash
shopt -s globstar 2>/dev/null || true
grep -Ersq '^[[:space:]]*\*[[:space:]]+hard[[:space:]]+core[[:space:]]+0\b' /etc/security/limits.conf /etc/security/limits.d 2>/dev/null || exit 1
[ "$(sysctl -n fs.suid_dumpable 2>/dev/null)" = "0" ] || exit 1
grep -Ersq '^[[:space:]]*fs\.suid_dumpable[[:space:]]*=[[:space:]]*0\b' /etc/sysctl.conf /etc/sysctl.d 2>/dev/null || exit 1
if [ -e /etc/systemd/coredump.conf ] || [ -d /etc/systemd/coredump.conf.d ]; then
  grep -Ehs '^[[:space:]]*Storage[[:space:]]*=' /etc/systemd/coredump.conf /etc/systemd/coredump.conf.d/*.conf 2>/dev/null | tail -1 | grep -q 'none' || exit 1
fi
exit 0
