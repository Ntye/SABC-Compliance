#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
grep -Ersl 'timestamp_timeout' /etc/sudoers /etc/sudoers.d 2>/dev/null | while read -r f; do
  sed -ri 's/timestamp_timeout\s*=\s*-?[0-9]+/timestamp_timeout=15/g' "$f"
done
visudo -cf /etc/sudoers >/dev/null || exit 1
exit 0
