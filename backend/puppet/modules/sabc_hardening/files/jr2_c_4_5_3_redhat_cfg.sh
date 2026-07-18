#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'typeset -xr TMOUT=900\n' > /etc/profile.d/60-criclo-tmout.sh
exit 0
