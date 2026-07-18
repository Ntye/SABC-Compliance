#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q aide >/dev/null 2>&1 || exit 0
for t in /usr/sbin/auditctl /usr/sbin/auditd /usr/sbin/ausearch /usr/sbin/aureport /usr/sbin/autrace /usr/sbin/augenrules; do
  grep -Eq "^\s*${t}\s" /etc/aide.conf 2>/dev/null || \
    printf '%s p+i+n+u+g+s+b+acl+xattrs+sha512\n' "$t" >> /etc/aide.conf
done
exit 0
