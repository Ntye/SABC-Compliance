#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
cfg=/etc/ssh/sshd_config
if grep -Eiq '^\s*Include\s+/etc/ssh/sshd_config.d' "$cfg" && [ -d /etc/ssh/sshd_config.d ]; then
  printf 'Ciphers aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr\n' > /etc/ssh/sshd_config.d/60-criclo-ciphers.conf
else
  sed -ri 's/^\s*#?\s*Ciphers\b.*/Ciphers aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr/I' "$cfg"
  grep -Eiq '^\s*Ciphers\b' "$cfg" || printf 'Ciphers aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr\n' >> "$cfg"
fi
sshd -t || exit 1
systemctl reload sshd 2>/dev/null || true
exit 0
