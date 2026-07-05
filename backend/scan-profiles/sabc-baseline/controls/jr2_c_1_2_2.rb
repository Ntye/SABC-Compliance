control 'JR2.C.1.2.2' do
  title 'Ensure filesystem integrity is regularly checked.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_2_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Prs '^([^#\n\r]+\h+)?(\/usr\/s?bin\/|^\h*)aide(\.wrapper)?\h+(--check|([^#\n\r]+\h+)?\$AIDEARGS)\b' /etc/cron.* /etc/crontab /var/spool/cron/
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Prs '^([^#\n\r]+\h+)?(\/usr\/s?bin\/|^\h*)aide(\.wrapper)?\h+(--check|([^#\n\r]+\h+)?\$AIDEARGS)\b' /etc/cron.* /etc/crontab /var/spool/cron/
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
