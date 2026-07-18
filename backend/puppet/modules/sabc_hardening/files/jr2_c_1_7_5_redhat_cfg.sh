#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q gdm >/dev/null 2>&1 || exit 0
mkdir -p /etc/dconf/db/local.d/locks /etc/dconf/profile
grep -q '^system-db:local$' /etc/dconf/profile/user 2>/dev/null || {
  printf 'user-db:user\nsystem-db:local\n' > /etc/dconf/profile/user
}
printf '[org/gnome/desktop/media-handling]\nautomount=false\nautomount-open=false\n' > /etc/dconf/db/local.d/60-criclo
printf '/org/gnome/desktop/media-handling/automount\n/org/gnome/desktop/media-handling/automount-open\n' > /etc/dconf/db/local.d/locks/60-criclo
dconf update
