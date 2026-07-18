#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
sed -ri 's/^\s*#?\s*PASS_MIN_DAYS\b.*/PASS_MIN_DAYS 1/' /etc/login.defs
grep -Eq '^\s*PASS_MIN_DAYS\b' /etc/login.defs || printf 'PASS_MIN_DAYS 1\n' >> /etc/login.defs
awk -F: '($2!~/^[!*]/) {print $1}' /etc/shadow | while read -r u; do chage --mindays 1 "$u"; done
