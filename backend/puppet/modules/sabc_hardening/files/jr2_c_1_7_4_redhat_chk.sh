#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 101
grep -Eqrs '/org/gnome/desktop/session/idle-delay' /etc/dconf/db/*/locks/ || exit 1
grep -Eqrs '/org/gnome/desktop/screensaver/lock-enabled' /etc/dconf/db/*/locks/ || exit 1
exit 0
