control 'JR2.C.1.1.5.2' do
  title 'Ensure noexec option set on /var/log partition.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_1_5_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /var/log | grep -v 'noexec'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /var/log | grep -v 'noexec'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
