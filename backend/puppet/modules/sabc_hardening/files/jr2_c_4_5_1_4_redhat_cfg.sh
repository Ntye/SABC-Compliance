#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
useradd -D -f 30
awk -F: '($2!~/^[!*]/) {print $1}' /etc/shadow | while read -r u; do
  chage --inactive 30 "$u"
done
exit 0
