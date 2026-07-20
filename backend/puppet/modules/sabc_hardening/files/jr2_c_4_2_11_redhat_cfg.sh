#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
cfg=/etc/ssh/sshd_config
if grep -Eiq '^\s*Include\s+/etc/ssh/sshd_config.d' "$cfg" && [ -d /etc/ssh/sshd_config.d ]; then
  printf 'IgnoreRhosts yes\n' > /etc/ssh/sshd_config.d/60-criclo-ignorerhosts.conf
else
  sed -ri 's/^\s*#?\s*IgnoreRhosts\b.*/IgnoreRhosts yes/I' "$cfg"
  grep -Eiq '^\s*IgnoreRhosts\b' "$cfg" || printf 'IgnoreRhosts yes\n' >> "$cfg"
fi
sshd -t || exit 1
systemctl reload sshd 2>/dev/null || true
exit 0
