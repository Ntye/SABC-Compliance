#!/bin/bash
shopt -s globstar 2>/dev/null || true
grep -Eqs '^[[:space:]]*auth[[:space:]]+(required|requisite)[[:space:]]+pam_wheel\.so[[:space:]].*use_uid.*group=' /etc/pam.d/su || exit 1
g=$(grep -Eos 'group=[^[:space:]]+' /etc/pam.d/su | head -1 | cut -d= -f2)
[ -n "$g" ] || exit 1
getent group "$g" >/dev/null 2>&1 || exit 1
[ -z "$(getent group "$g" | cut -d: -f4)" ] || exit 1
exit 0
