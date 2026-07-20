#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
mkdir -p /etc/security/pwquality.conf.d
printf 'dictcheck = 1\n' > /etc/security/pwquality.conf.d/60-criclo-dictcheck.conf
exit 0
