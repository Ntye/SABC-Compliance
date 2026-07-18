#!/bin/bash
shopt -s globstar 2>/dev/null || true
[ "$(getenforce 2>/dev/null)" = "Enforcing" ] || exit 1
grep -Eqs '^[[:space:]]*SELINUX=enforcing' /etc/selinux/config || exit 1
exit 0
