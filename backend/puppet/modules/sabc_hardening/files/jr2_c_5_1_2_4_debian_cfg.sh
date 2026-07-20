#!/bin/bash
shopt -s globstar 2>/dev/null || true
changed=0
for f in /etc/rsyslog.conf /etc/rsyslog.d/*.conf; do
  [ -e "$f" ] || continue
  if grep -Eqs '^[[:space:]]*(module\(load="im(tcp|udp)"\)|input\(type="im(tcp|udp)"|\$ModLoad[[:space:]]+im(tcp|udp)|\$(InputTCPServerRun|UDPServerRun))' "$f"; then
    sed -ri 's|^([[:space:]]*)(module\(load="im(tcp\|udp)"\).*)|\1# \2|; s|^([[:space:]]*)(input\(type="im(tcp\|udp)".*)|\1# \2|; s|^([[:space:]]*)(\$ModLoad[[:space:]]+im(tcp\|udp).*)|\1# \2|; s|^([[:space:]]*)(\$(InputTCPServerRun\|UDPServerRun).*)|\1# \2|' "$f"
    changed=1
  fi
done
[ "$changed" -eq 1 ] && systemctl restart rsyslog >/dev/null 2>&1
exit 0
