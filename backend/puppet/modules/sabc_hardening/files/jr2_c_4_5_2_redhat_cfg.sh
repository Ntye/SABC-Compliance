#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
sed -ri 's/^\s*UMASK\s+.*/UMASK 027/' /etc/login.defs
grep -Eq '^\s*UMASK\b' /etc/login.defs || printf 'UMASK 027\n' >> /etc/login.defs
printf 'umask 027\n' > /etc/profile.d/60-criclo-umask.sh
exit 0
