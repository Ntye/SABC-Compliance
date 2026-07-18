#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 101
mkdir -p /etc/dconf/db/gdm.d/locks /etc/dconf/profile
grep -qs '^system-db:gdm' /etc/dconf/profile/gdm 2>/dev/null || printf 'user-db:user\nsystem-db:gdm\nfile-db:/usr/share/gdm/greeter-dconf-defaults\n' > /etc/dconf/profile/gdm
mkdir -p /etc/dconf/db/local.d/locks
printf '/org/gnome/desktop/media-handling/automount\n/org/gnome/desktop/media-handling/automount-open\n' > /etc/dconf/db/local.d/locks/00-media
dconf update
exit 0
