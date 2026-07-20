#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
umin=$(awk '/^\s*UID_MIN/{print $2}' /etc/login.defs)
[ -n "$umin" ] || umin=1000
awk -F: -v m="$umin" '($1!~/^(root|halt|sync|shutdown|nfsnobody)$/ && ($3<m || $3==65534) && $7!~/(nologin|\/bin\/false)$/) {print $1}' /etc/passwd | \
while read -r u; do
  usermod -s /sbin/nologin "$u"
  usermod -L "$u"
done
exit 0
