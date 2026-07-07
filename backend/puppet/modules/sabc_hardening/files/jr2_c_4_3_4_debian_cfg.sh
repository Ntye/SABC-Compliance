#!/bin/bash
shopt -s globstar 2>/dev/null || true
files=$(grep -rEls '^[^#]*\!authenticate' /etc/sudoers /etc/sudoers.d 2>/dev/null)
[ -n "$files" ] || exit 0
for f in $files; do
  cp -p "$f" "$f.sabc.bak"
  sed -ri 's/[[:space:]]*\!authenticate\b//g' "$f"
  if visudo -cf "$f" >/dev/null; then
    rm -f "$f.sabc.bak"
  else
    mv "$f.sabc.bak" "$f"
  fi
done
exit 0
