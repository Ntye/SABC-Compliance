#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
grep -Eiq '^\s*ENCRYPT_METHOD\s+(SHA512|YESCRYPT)\b' /etc/login.defs || exit 1
grep -E 'pam_unix\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth 2>/dev/null | grep -Eq '\b(md5|des|bigcrypt|blowfish)\b' && exit 1
exit 0
