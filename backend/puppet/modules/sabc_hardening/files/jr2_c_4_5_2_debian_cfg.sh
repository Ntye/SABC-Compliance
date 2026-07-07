#!/bin/bash
shopt -s globstar 2>/dev/null || true
if grep -Eqs '^[[:space:]]*#?[[:space:]]*UMASK[[:space:]]' /etc/login.defs; then
  sed -ri 's/^[[:space:]]*#?[[:space:]]*UMASK[[:space:]]+[0-9]+/UMASK\t\t027/' /etc/login.defs
else
  printf 'UMASK\t\t027\n' >> /etc/login.defs
fi
printf 'umask 027\n' > /etc/profile.d/50-sabc-umask.sh
chmod 644 /etc/profile.d/50-sabc-umask.sh
exit 0
