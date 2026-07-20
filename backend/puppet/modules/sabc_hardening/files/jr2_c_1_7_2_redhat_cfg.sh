#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 0
mkdir -p /etc/dconf/db/gdm.d/locks /etc/dconf/profile
grep -q '^system-db:gdm$' /etc/dconf/profile/user 2>/dev/null || {
  printf 'user-db:user\nsystem-db:gdm\n' > /etc/dconf/profile/user
}
printf '[org/gnome/login-screen]\ndisable-user-list=true\n' > /etc/dconf/db/gdm.d/60-criclo
printf '/org/gnome/login-screen/disable-user-list\n' > /etc/dconf/db/gdm.d/locks/60-criclo
dconf update
