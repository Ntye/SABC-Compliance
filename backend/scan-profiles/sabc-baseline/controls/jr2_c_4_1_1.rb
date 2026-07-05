control 'JR2.C.4.1.1' do
  title 'Ensure cron daemon is enabled and active.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_1_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled cron
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled cron
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
