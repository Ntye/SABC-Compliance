#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 101
mkdir -p /etc/dconf/db/gdm.d/locks /etc/dconf/profile
grep -qs '^system-db:gdm' /etc/dconf/profile/gdm 2>/dev/null || printf 'user-db:user\nsystem-db:gdm\nfile-db:/usr/share/gdm/greeter-dconf-defaults\n' > /etc/dconf/profile/gdm
printf '[org/gnome/login-screen]\ndisable-user-list=true\n' > /etc/dconf/db/gdm.d/02-login
dconf update
exit 0
