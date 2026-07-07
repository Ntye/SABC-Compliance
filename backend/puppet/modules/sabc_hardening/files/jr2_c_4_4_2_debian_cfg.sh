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

            f=/etc/security/faillock.conf
            [ -e "$f" ] || touch "$f"
            set_kv deny 5 "$f"
            set_kv unlock_time 900 "$f"
            cat > /usr/share/pam-configs/sabc-faillock <<'PAMEOF'
Name: Enforce failed login attempt counter (faillock)
Default: yes
Priority: 0
Auth-Type: Primary
Auth:
	[default=die] pam_faillock.so authfail
Auth-Initial:
	requisite pam_faillock.so preauth
PAMEOF
            cat > /usr/share/pam-configs/sabc-faillock-notify <<'PAMEOF'
Name: Notify on failed login attempts (faillock)
Default: yes
Priority: 1024
Account-Type: Primary
Account:
	required pam_faillock.so
PAMEOF
            pam-auth-update --package >/dev/null 2>&1
            exit 0
