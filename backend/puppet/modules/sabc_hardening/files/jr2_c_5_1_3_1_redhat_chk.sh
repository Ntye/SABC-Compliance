#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q aide >/dev/null 2>&1 || exit 101
for t in /usr/sbin/auditctl /usr/sbin/auditd /usr/sbin/ausearch /usr/sbin/aureport /usr/sbin/autrace /usr/sbin/augenrules; do
  grep -Eq "^\s*${t}\s+.*(sha512|sha256)" /etc/aide.conf /etc/aide.conf.d/*.conf 2>/dev/null || exit 1
done
exit 0
