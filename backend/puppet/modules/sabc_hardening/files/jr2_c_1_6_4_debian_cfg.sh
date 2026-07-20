#!/bin/bash
shopt -s globstar 2>/dev/null || true
[ -e /etc/motd ] || exit 0
chown root:root /etc/motd
chmod 644 /etc/motd
exit 0
