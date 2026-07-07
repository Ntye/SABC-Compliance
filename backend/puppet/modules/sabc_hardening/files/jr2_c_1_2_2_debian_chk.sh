#!/bin/bash
shopt -s globstar 2>/dev/null || true
crontab -u root -l 2>/dev/null | grep -Eq '(^|/)(aide|aide\.wrapper)\b' && exit 0
grep -Ersq '(^|/)(aide|aide\.wrapper)\b' /etc/cron.d /etc/cron.daily 2>/dev/null && exit 0
systemctl is-enabled dailyaidecheck.timer >/dev/null 2>&1 && exit 0
systemctl is-enabled aidecheck.timer >/dev/null 2>&1 && exit 0
exit 1
