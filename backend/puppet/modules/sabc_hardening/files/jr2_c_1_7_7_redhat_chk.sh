#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 101
grep -Eqrs 'autorun-never=true' /etc/dconf/db/gdm.d/ || exit 1
exit 0
