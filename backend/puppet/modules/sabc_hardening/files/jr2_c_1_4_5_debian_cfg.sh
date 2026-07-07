#!/bin/bash
shopt -s globstar 2>/dev/null || true
printf '* hard core 0\n' > /etc/security/limits.d/50-sabc-core.conf
printf 'fs.suid_dumpable = 0\n' > /etc/sysctl.d/60-sabc-coredump.conf
sysctl -w fs.suid_dumpable=0 >/dev/null
if [ -e /etc/systemd/coredump.conf ] || [ -d /etc/systemd/coredump.conf.d ]; then
  mkdir -p /etc/systemd/coredump.conf.d
  printf '[Coredump]\nStorage=none\nProcessSizeMax=0\n' > /etc/systemd/coredump.conf.d/60-sabc.conf
fi
exit 0
