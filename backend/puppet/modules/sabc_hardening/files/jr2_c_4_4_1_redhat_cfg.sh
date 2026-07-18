#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
mkdir -p /etc/security/pwquality.conf.d
printf 'minlen = 14\nminclass = 4\n' > /etc/security/pwquality.conf.d/60-criclo-pwquality.conf
exit 0
