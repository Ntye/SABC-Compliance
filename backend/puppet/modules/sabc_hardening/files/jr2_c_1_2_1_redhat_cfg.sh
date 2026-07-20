#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
dnf install -y aide
if [ ! -f /var/lib/aide/aide.db.gz ]; then
  aide --init && mv -f /var/lib/aide/aide.db.new.gz /var/lib/aide/aide.db.gz
fi
exit 0
