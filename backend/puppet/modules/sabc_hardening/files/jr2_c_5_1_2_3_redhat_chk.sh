#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q rsyslog >/dev/null 2>&1 || exit 101
m=$(grep -Ersh '^\$FileCreateMode\s+[0-7]+' /etc/rsyslog.conf /etc/rsyslog.d 2>/dev/null | awk '{print $2}' | tail -n1)
[ -n "$m" ] || exit 1
[ $(( 8#$m & 8#0137 )) -eq 0 ]
