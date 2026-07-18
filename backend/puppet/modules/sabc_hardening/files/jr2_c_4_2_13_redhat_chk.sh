#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
command -v sshd >/dev/null 2>&1 || exit 101
T=$(sshd -T 2>/dev/null) || exit 1
echo "$T" | grep '^macs ' | grep -Eq '(hmac-md5|hmac-ripemd160|hmac-sha1-96|umac-64)' && exit 1
exit 0
