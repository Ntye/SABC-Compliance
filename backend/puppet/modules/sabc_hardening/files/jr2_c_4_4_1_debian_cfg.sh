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

            dpkg-query -W libpam-pwquality >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get -y install libpam-pwquality >/dev/null
            f=/etc/security/pwquality.conf
            [ -e "$f" ] || touch "$f"
            set_kv minlen 14 "$f"
            set_kv minclass 4 "$f"
            exit 0
