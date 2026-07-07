#!/bin/bash
shopt -s globstar 2>/dev/null || true
set_kv() {
  k="$1"; v="$2"; f="$3"
  if grep -Eq "^[[:space:]]*#?[[:space:]]*$k[[:space:]]*=" "$f" 2>/dev/null; then
    sed -ri "s|^[[:space:]]*#?[[:space:]]*($k)[[:space:]]*=.*|\1 = $v|" "$f"
  else
    printf '%s = %s\n' "$k" "$v" >> "$f"
  fi
}

            f=/etc/security/pwquality.conf
            [ -e "$f" ] || touch "$f"
            set_kv dictcheck 1 "$f"
            exit 0
