#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
find -L /var/log -type f -perm /o+w ! -path '*/journal/*' -exec chmod o-w {} + 2>/dev/null
for f in /var/log/secure /var/log/messages /var/log/maillog /var/log/cron; do
  [ -e "$f" ] && chmod u-x,g-wx,o-rwx "$f"
done
exit 0
