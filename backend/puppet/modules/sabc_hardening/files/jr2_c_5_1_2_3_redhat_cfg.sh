#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q rsyslog >/dev/null 2>&1 || exit 0
printf '$FileCreateMode 0640\n' > /etc/rsyslog.d/60-criclo-filemode.conf
systemctl try-restart rsyslog.service 2>/dev/null || true
exit 0
