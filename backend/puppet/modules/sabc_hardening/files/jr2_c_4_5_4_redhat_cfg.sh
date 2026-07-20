#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
mkdir -p /etc/security/pwquality.conf.d
printf 'maxrepeat = 3\n' > /etc/security/pwquality.conf.d/60-criclo-maxrepeat.conf
exit 0
