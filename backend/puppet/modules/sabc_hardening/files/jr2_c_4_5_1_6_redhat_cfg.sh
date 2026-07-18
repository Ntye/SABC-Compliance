#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
mkdir -p /etc/security/pwquality.conf.d
printf 'difok = 2\n' > /etc/security/pwquality.conf.d/60-criclo-difok.conf
exit 0
