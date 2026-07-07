#!/bin/bash
shopt -s globstar 2>/dev/null || true
if [ -d /etc/aide/aide.conf.d ]; then
  out=/etc/aide/aide.conf.d/70_sabc_audit_tools
else
  out=/etc/aide.conf
fi
for t in auditctl auditd ausearch aureport autrace augenrules; do
  p=$(command -v "$t" 2>/dev/null || echo "/usr/sbin/$t")
  grep -qs "^$p[[:space:]]" "$out" 2>/dev/null || printf '%s p+i+n+u+g+s+b+acl+xattrs+sha512\n' "$p" >> "$out"
done
exit 0
