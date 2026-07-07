#!/bin/bash
shopt -s globstar 2>/dev/null || true
if [ -d /etc/aide/aide.conf.d ]; then
  conf_glob='/etc/aide/aide.conf /etc/aide/aide.conf.d/*'
else
  conf_glob='/etc/aide.conf'
fi
for t in auditctl auditd ausearch aureport autrace augenrules; do
  p=$(command -v "$t" 2>/dev/null || echo "/usr/sbin/$t")
  grep -Ehs "^$p[[:space:]]" $conf_glob 2>/dev/null | grep -q 'sha512' || exit 1
done
exit 0
