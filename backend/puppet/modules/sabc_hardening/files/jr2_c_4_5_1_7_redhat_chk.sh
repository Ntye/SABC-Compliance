#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q libpwquality >/dev/null 2>&1 || exit 1
v=$(awk -F= '/^\s*dictcheck\s*=/ {gsub(/ /,"",$2); print $2}' \
    /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -n1)
[ -z "$v" ] || [ "$v" != "0" ]
