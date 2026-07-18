#!/bin/bash
shopt -s globstar 2>/dev/null || true
grubby --update-kernel ALL --remove-args 'selinux=0 enforcing=0' 2>/dev/null || true
if [ -f /etc/default/grub ]; then
  sed -ri 's/\bselinux=0\b//g; s/\benforcing=0\b//g' /etc/default/grub
fi
exit 0
