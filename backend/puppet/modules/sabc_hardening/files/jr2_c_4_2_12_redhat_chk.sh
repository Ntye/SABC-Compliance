#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
command -v sshd >/dev/null 2>&1 || exit 101
T=$(sshd -T 2>/dev/null) || exit 1
echo "$T" | grep '^ciphers ' | grep -Eq '(3des-cbc|aes128-cbc|aes192-cbc|aes256-cbc|rc4|blowfish-cbc|cast128-cbc)' && exit 1
exit 0
