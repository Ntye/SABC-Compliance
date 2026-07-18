#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
sed -ri 's/^\s*#?\s*PASS_MAX_DAYS\b.*/PASS_MAX_DAYS 365/' /etc/login.defs
grep -Eq '^\s*PASS_MAX_DAYS\b' /etc/login.defs || printf 'PASS_MAX_DAYS 365\n' >> /etc/login.defs
awk -F: '($2!~/^[!*]/) {print $1}' /etc/shadow | while read -r u; do chage --maxdays 365 "$u"; done
