#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'install usb-storage /bin/false\nblacklist usb-storage\n' > /etc/modprobe.d/usb-storage.conf
modprobe -r usb-storage 2>/dev/null || true
exit 0
