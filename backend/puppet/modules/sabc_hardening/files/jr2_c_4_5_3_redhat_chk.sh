#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
t=$(grep -Ersho 'TMOUT=[0-9]+' /etc/profile /etc/profile.d /etc/bashrc 2>/dev/null | grep -Eo '[0-9]+' | tail -n1)
[ -n "$t" ] && [ "$t" -ge 1 ] && [ "$t" -le 900 ]
