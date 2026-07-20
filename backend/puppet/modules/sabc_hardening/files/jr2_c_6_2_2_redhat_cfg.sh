#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
awk -F: '($2 == "") {print $1}' /etc/shadow | while read -r u; do
  passwd -l "$u"
done
exit 0
