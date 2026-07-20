#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
sed -ri 's/^\s*#?\s*PASS_WARN_AGE\b.*/PASS_WARN_AGE 7/' /etc/login.defs
grep -Eq '^\s*PASS_WARN_AGE\b' /etc/login.defs || printf 'PASS_WARN_AGE 7\n' >> /etc/login.defs
awk -F: '($2!~/^[!*]/) {print $1}' /etc/shadow | while read -r u; do chage --warndays 7 "$u"; done
