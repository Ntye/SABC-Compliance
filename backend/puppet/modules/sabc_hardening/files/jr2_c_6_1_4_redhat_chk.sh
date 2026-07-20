#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
f=/etc/group-
[ -e "$f" ] || exit 0
set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
[ "$o" = "root" ] || exit 1
{ [ "$g" = "root" ]; } || exit 1
[ $(( 8#$m & ~8#644 & 8#7777 )) -eq 0 ] || exit 1
exit 0
