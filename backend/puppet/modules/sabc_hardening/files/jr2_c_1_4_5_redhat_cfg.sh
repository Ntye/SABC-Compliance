#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf '* hard core 0\n' > /etc/security/limits.d/60-criclo-core.conf
printf 'fs.suid_dumpable = 0\n' > /etc/sysctl.d/60-criclo-coredump.conf
sysctl -w fs.suid_dumpable=0
if rpm -q systemd-coredump >/dev/null 2>&1; then
  mkdir -p /etc/systemd/coredump.conf.d
  printf '[Coredump]\nStorage=none\nProcessSizeMax=0\n' > /etc/systemd/coredump.conf.d/60-criclo.conf
fi
exit 0
