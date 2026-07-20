#!/bin/bash
shopt -s globstar 2>/dev/null || true
[ -e /etc/motd ] || exit 0
[ "$(stat -c '%a %U %G' /etc/motd)" = "644 root root" ] && exit 0
exit 1
