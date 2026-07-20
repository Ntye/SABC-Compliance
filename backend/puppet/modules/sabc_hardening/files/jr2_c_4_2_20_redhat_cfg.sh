#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
cfg=/etc/ssh/sshd_config
if grep -Eiq '^\s*Include\s+/etc/ssh/sshd_config.d' "$cfg" && [ -d /etc/ssh/sshd_config.d ]; then
  printf 'ClientAliveInterval 300\nClientAliveCountMax 3\n' > /etc/ssh/sshd_config.d/60-criclo-clientalive.conf
else
  sed -ri 's/^\s*#?\s*ClientAliveInterval\b.*/ClientAliveInterval 300/I' "$cfg"
  grep -Eiq '^\s*ClientAliveInterval\b' "$cfg" || printf 'ClientAliveInterval 300\n' >> "$cfg"
  sed -ri 's/^\s*#?\s*ClientAliveCountMax\b.*/ClientAliveCountMax 3/I' "$cfg"
  grep -Eiq '^\s*ClientAliveCountMax\b' "$cfg" || printf 'ClientAliveCountMax 3\n' >> "$cfg"
fi
sshd -t || exit 1
systemctl reload sshd 2>/dev/null || true
exit 0
