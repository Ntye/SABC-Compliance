#!/bin/bash
shopt -s globstar 2>/dev/null || true
if command -v sshd >/dev/null 2>&1; then
  sshd -T 2>/dev/null | grep -Eqi '^(allowusers|allowgroups|denyusers|denygroups)[[:space:]]+[^[:space:]]' && exit 0
fi
cat /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | grep -Eqi '^[[:space:]]*(Allow|Deny)(Users|Groups)[[:space:]]+[^[:space:]]' && exit 0
exit 1
