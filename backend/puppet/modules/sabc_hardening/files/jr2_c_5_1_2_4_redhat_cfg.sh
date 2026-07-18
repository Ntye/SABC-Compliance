#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q rsyslog >/dev/null 2>&1 || exit 0
for f in /etc/rsyslog.conf /etc/rsyslog.d/*.conf; do
  [ -f "$f" ] || continue
  sed -ri 's/^(\s*module\(load="im(tcp|udp)"\).*)/#\1/' "$f"
  sed -ri 's/^(\s*input\(type="im(tcp|udp)".*)/#\1/' "$f"
  sed -ri 's/^(\s*\$ModLoad\s+im(tcp|udp).*)/#\1/' "$f"
  sed -ri 's/^(\s*\$(InputTCPServerRun|UDPServerRun).*)/#\1/' "$f"
done
systemctl try-restart rsyslog.service 2>/dev/null || true
exit 0
