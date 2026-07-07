#!/bin/bash
shopt -s globstar 2>/dev/null || true
mkdir -p /etc/systemd/journald.conf.d
f=/etc/systemd/journald.conf.d/60-sabc.conf
grep -qs '^\[Journal\]' "$f" 2>/dev/null || printf '[Journal]\n' >> "$f"
if grep -qs '^Compress=' "$f"; then
  sed -ri 's/^Compress=.*/Compress=yes/' "$f"
else
  printf 'Compress=yes\n' >> "$f"
fi
systemctl restart systemd-journald >/dev/null 2>&1
exit 0
