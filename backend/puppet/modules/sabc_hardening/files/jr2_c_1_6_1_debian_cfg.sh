#!/bin/bash
shopt -s globstar 2>/dev/null || true
[ -e /etc/motd ] || exit 0
os_id=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
sed -ri "s/\\\\[mrsv]//g" /etc/motd
[ -n "$os_id" ] && sed -ri "s/$os_id//gI" /etc/motd
exit 0
