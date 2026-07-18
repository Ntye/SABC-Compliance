#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
cfg=/etc/ssh/sshd_config
if grep -Eiq '^\s*Include\s+/etc/ssh/sshd_config.d' "$cfg" && [ -d /etc/ssh/sshd_config.d ]; then
  printf 'LoginGraceTime 60\n' > /etc/ssh/sshd_config.d/60-criclo-logingracetime.conf
else
  sed -ri 's/^\s*#?\s*LoginGraceTime\b.*/LoginGraceTime 60/I' "$cfg"
  grep -Eiq '^\s*LoginGraceTime\b' "$cfg" || printf 'LoginGraceTime 60\n' >> "$cfg"
fi
sshd -t || exit 1
systemctl reload sshd 2>/dev/null || true
exit 0
