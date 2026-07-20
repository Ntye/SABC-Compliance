#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
r=$(awk -F= '/^\s*remember\s*=/ {gsub(/ /,"",$2); print $2}' /etc/security/pwhistory.conf 2>/dev/null | tail -n1)
[ -z "$r" ] && r=$(grep -Eo 'pam_pwhistory\.so[^#]*remember=[0-9]+' /etc/pam.d/system-auth 2>/dev/null | grep -Eo '[0-9]+' | tail -n1)
[ -n "$r" ] && [ "$r" -ge 5 ]
