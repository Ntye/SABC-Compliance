control 'JR2.C.1.6.3' do
  title 'Ensure remote login warning banner is configured properly.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_6_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      cat /etc/issue.net
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      cat /etc/issue.net
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
