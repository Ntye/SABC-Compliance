#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
ok=0
for f in /boot/grub2/grub.cfg /boot/grub2/grubenv /boot/grub2/user.cfg; do
  [ -e "$f" ] || continue
  ok=1
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ "$o" = root ] && [ "$g" = root ] || exit 1
  [ $(( 8#$m & 8#0077 )) -eq 0 ] || exit 1
done
[ "$ok" -eq 1 ] && exit 0 || exit 101
