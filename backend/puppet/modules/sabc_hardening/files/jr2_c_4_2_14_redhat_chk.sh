#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
command -v sshd >/dev/null 2>&1 || exit 101
T=$(sshd -T 2>/dev/null) || exit 1
echo "$T" | grep '^kexalgorithms ' | grep -Eq '(diffie-hellman-group1-sha1|diffie-hellman-group14-sha1|diffie-hellman-group-exchange-sha1)' && exit 1
exit 0
