#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
grep -Ersq '^\s*\*\s+hard\s+core\s+0\b' /etc/security/limits.conf /etc/security/limits.d 2>/dev/null || exit 1
[ "$(sysctl -n fs.suid_dumpable 2>/dev/null)" = "0" ] || exit 1
if rpm -q systemd-coredump >/dev/null 2>&1; then
  grep -Ersq '^\s*Storage\s*=\s*none' /etc/systemd/coredump.conf /etc/systemd/coredump.conf.d 2>/dev/null || exit 1
fi
exit 0
