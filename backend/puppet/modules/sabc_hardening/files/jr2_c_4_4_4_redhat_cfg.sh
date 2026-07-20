#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
sed -ri 's/^\s*#?\s*ENCRYPT_METHOD\b.*/ENCRYPT_METHOD SHA512/' /etc/login.defs
grep -Eq '^\s*ENCRYPT_METHOD\b' /etc/login.defs || printf 'ENCRYPT_METHOD SHA512\n' >> /etc/login.defs
exit 0
