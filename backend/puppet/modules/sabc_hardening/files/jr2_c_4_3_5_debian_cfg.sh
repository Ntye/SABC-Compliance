#!/bin/bash
shopt -s globstar 2>/dev/null || true
if grep -rEqs 'timestamp_timeout[[:space:]]*=' /etc/sudoers /etc/sudoers.d 2>/dev/null; then
  for f in $(grep -rEls 'timestamp_timeout[[:space:]]*=' /etc/sudoers /etc/sudoers.d 2>/dev/null); do
    cp -p "$f" "$f.sabc.bak"
    sed -ri 's/(timestamp_timeout[[:space:]]*=[[:space:]]*)-?[0-9]+/\115/g' "$f"
    if visudo -cf "$f" >/dev/null; then
      rm -f "$f.sabc.bak"
    else
      mv "$f.sabc.bak" "$f"
    fi
  done
else
  f=/etc/sudoers.d/90-sabc-defaults
  printf 'Defaults env_reset, timestamp_timeout=15\n' >> "$f"
  chmod 440 "$f"
  visudo -cf "$f" >/dev/null || { rm -f "$f"; exit 1; }
fi
exit 0
