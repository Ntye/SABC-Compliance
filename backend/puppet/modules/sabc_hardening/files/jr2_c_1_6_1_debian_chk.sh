#!/bin/bash
shopt -s globstar 2>/dev/null || true
[ -e /etc/motd ] || exit 0
os_id=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
grep -Eqis "(\\\\v|\\\\r|\\\\m|\\\\s|$os_id)" /etc/motd && exit 1
exit 0
