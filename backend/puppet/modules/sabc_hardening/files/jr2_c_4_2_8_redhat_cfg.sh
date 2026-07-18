#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
cfg=/etc/ssh/sshd_config
if grep -Eiq '^\s*Include\s+/etc/ssh/sshd_config.d' "$cfg" && [ -d /etc/ssh/sshd_config.d ]; then
  printf 'HostbasedAuthentication no\n' > /etc/ssh/sshd_config.d/60-criclo-hostbasedauthentication.conf
else
  sed -ri 's/^\s*#?\s*HostbasedAuthentication\b.*/HostbasedAuthentication no/I' "$cfg"
  grep -Eiq '^\s*HostbasedAuthentication\b' "$cfg" || printf 'HostbasedAuthentication no\n' >> "$cfg"
fi
sshd -t || exit 1
systemctl reload sshd 2>/dev/null || true
exit 0
