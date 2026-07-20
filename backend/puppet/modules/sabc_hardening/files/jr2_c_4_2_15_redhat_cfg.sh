#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
cfg=/etc/ssh/sshd_config
if grep -Eiq '^\s*Include\s+/etc/ssh/sshd_config.d' "$cfg" && [ -d /etc/ssh/sshd_config.d ]; then
  printf 'Banner /etc/issue.net\n' > /etc/ssh/sshd_config.d/60-criclo-banner.conf
else
  sed -ri 's/^\s*#?\s*Banner\b.*/Banner /etc/issue.net/I' "$cfg"
  grep -Eiq '^\s*Banner\b' "$cfg" || printf 'Banner /etc/issue.net\n' >> "$cfg"
fi
sshd -t || exit 1
systemctl reload sshd 2>/dev/null || true
exit 0
