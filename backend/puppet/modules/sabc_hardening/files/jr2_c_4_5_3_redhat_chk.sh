#!/bin/bash
shopt -s globstar 2>/dev/null || true
v=$(grep -Ehs 'TMOUT=' /etc/profile.d/*.sh /etc/profile /etc/bash.bashrc 2>/dev/null | grep -oE 'TMOUT=[0-9]+' | tail -1 | cut -d= -f2)
[ -n "$v" ] && [ "$v" -ge 1 ] && [ "$v" -le 900 ] && exit 0
exit 1
