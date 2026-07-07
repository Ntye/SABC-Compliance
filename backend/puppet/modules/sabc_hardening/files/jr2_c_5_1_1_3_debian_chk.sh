#!/bin/bash
shopt -s globstar 2>/dev/null || true
grep -Ehs '^[[:space:]]*Storage[[:space:]]*=' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*.conf 2>/dev/null | tail -1 | grep -qi 'persistent' && exit 0
exit 1
