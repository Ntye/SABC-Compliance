#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
for f in /boot/grub2/grub.cfg /boot/grub2/grubenv /boot/grub2/user.cfg; do
  [ -e "$f" ] || continue
  chown root:root "$f"
  chmod u-x,go-rwx "$f"
done
exit 0
