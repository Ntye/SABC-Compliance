#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
cfg=/etc/ssh/sshd_config
if grep -Eiq '^\s*Include\s+/etc/ssh/sshd_config.d' "$cfg" && [ -d /etc/ssh/sshd_config.d ]; then
  printf 'MaxAuthTries 4\n' > /etc/ssh/sshd_config.d/60-criclo-maxauthtries.conf
else
  sed -ri 's/^\s*#?\s*MaxAuthTries\b.*/MaxAuthTries 4/I' "$cfg"
  grep -Eiq '^\s*MaxAuthTries\b' "$cfg" || printf 'MaxAuthTries 4\n' >> "$cfg"
fi
sshd -t || exit 1
systemctl reload sshd 2>/dev/null || true
exit 0
