#!/bin/bash
shopt -s globstar 2>/dev/null || true
cat /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | grep -Eqi '^[[:space:]]*(Allow|Deny)(Users|Groups)[[:space:]]+[^[:space:]]' && exit 0
d=/etc/ssh/sshd_config.d
mkdir -p "$d"
f="$d/60-sabc-access.conf"
printf 'DenyUsers nobody\n' > "$f"
if command -v sshd >/dev/null 2>&1 && ! sshd -t >/dev/null 2>&1; then
  rm -f "$f"
  exit 1
fi
systemctl reload ssh >/dev/null 2>&1 || systemctl reload sshd >/dev/null 2>&1
exit 0
