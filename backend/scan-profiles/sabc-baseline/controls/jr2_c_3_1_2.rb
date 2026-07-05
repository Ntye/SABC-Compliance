control 'JR2.C.3.1.2' do
  title 'Ensure bluetooth is disabled.'
  impact 0.7
  tag cis_level: 2
  tag control_key: 'jr2_c_3_1_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled bluetooth.service | grep '^enabled'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled bluetooth.service | grep '^enabled'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
