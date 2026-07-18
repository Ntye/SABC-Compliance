#!/bin/bash
shopt -s globstar 2>/dev/null || true
# Fail if any current kernel arg disables SELinux (selinux=0 / enforcing=0).
if grubby --info=ALL 2>/dev/null | grep -Eq 'selinux=0|enforcing=0'; then exit 1; fi
grep -Eqs 'selinux=0|enforcing=0' /etc/default/grub && exit 1
exit 0
