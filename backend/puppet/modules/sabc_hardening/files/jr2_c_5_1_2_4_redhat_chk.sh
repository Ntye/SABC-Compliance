#!/bin/bash
shopt -s globstar 2>/dev/null || true
grep -Ehs '^[[:space:]]*(module\(load="im(tcp|udp)"\)|input\(type="im(tcp|udp)"|\$ModLoad[[:space:]]+im(tcp|udp)|\$(InputTCPServerRun|UDPServerRun))' /etc/rsyslog.conf /etc/rsyslog.d/*.conf 2>/dev/null | grep -q . && exit 1
exit 0
