#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 101
grep -Eqrs 'idle-delay=uint32 [1-9]' /etc/dconf/db/local.d/ /etc/dconf/db/gdm.d/ || exit 1
grep -Eqrs 'lock-enabled=true' /etc/dconf/db/local.d/ /etc/dconf/db/gdm.d/ || exit 1
exit 0
