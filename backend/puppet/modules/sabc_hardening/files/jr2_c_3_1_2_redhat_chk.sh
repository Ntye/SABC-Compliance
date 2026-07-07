#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q bluez >/dev/null 2>&1 || exit 0
systemctl is-active bluetooth 2>/dev/null | grep -qx active && exit 1
systemctl is-enabled bluetooth 2>/dev/null | grep -q '^enabled' && exit 1
exit 0
