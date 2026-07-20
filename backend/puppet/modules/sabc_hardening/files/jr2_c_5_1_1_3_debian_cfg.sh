#!/bin/bash
shopt -s globstar 2>/dev/null || true
mkdir -p /etc/systemd/journald.conf.d /var/log/journal
f=/etc/systemd/journald.conf.d/60-sabc.conf
grep -qs '^\[Journal\]' "$f" 2>/dev/null || printf '[Journal]\n' >> "$f"
if grep -qs '^Storage=' "$f"; then
  sed -ri 's/^Storage=.*/Storage=persistent/' "$f"
else
  printf 'Storage=persistent\n' >> "$f"
fi
systemctl restart systemd-journald >/dev/null 2>&1
exit 0
