control 'JR2.C.1.2.2' do
  title 'Ensure filesystem integrity is regularly checked.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_2_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
#!/bin/bash
crontab -u root -l 2>/dev/null | grep -Eq '(^|/)(aide|aide\.wrapper)\b' && exit 0
grep -Ersq '(^|/)(aide|aide\.wrapper)\b' /etc/cron.d /etc/cron.daily 2>/dev/null && exit 0
systemctl is-enabled dailyaidecheck.timer >/dev/null 2>&1 && exit 0
systemctl is-enabled aidecheck.timer >/dev/null 2>&1 && exit 0
exit 1
    SABC_V
    if v_debian.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_debian do
        its('exit_status') { should cmp 0 }
      end
    end
  end
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
#!/usr/bin/env bash
rpm -q aide >/dev/null 2>&1 || exit 1
grep -Ersq '^([^#]+\s)?(/usr/sbin/)?aide(\.wrapper)?\s(--check|.*--check)' \
  /etc/cron.d /etc/cron.daily /etc/cron.weekly /etc/crontab /var/spool/cron 2>/dev/null && exit 0
systemctl is-enabled aidecheck.timer 2>/dev/null | grep -q enabled && exit 0
exit 1
    SABC_V
    if v_redhat.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_redhat do
        its('exit_status') { should cmp 0 }
      end
    end
  end
end
