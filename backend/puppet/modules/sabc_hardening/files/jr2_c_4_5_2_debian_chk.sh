#!/bin/bash
shopt -s globstar 2>/dev/null || true
grep -Eqs '^[[:space:]]*UMASK[[:space:]]+027' /etc/login.defs || exit 1
grep -Eqs '^[[:space:]]*umask[[:space:]]+027' /etc/profile.d/*.sh /etc/profile 2>/dev/null || exit 1
exit 0
