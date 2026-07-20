#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
cfg=/etc/ssh/sshd_config
if grep -Eiq '^\s*Include\s+/etc/ssh/sshd_config.d' "$cfg" && [ -d /etc/ssh/sshd_config.d ]; then
  printf 'LogLevel VERBOSE\n' > /etc/ssh/sshd_config.d/60-criclo-loglevel.conf
else
  sed -ri 's/^\s*#?\s*LogLevel\b.*/LogLevel VERBOSE/I' "$cfg"
  grep -Eiq '^\s*LogLevel\b' "$cfg" || printf 'LogLevel VERBOSE\n' >> "$cfg"
fi
sshd -t || exit 1
systemctl reload sshd 2>/dev/null || true
exit 0
