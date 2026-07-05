control 'JR2.C.1.1.2.4' do
  title 'Ensure nosuid option set on /tmp partition.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_1_2_4'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /tmp | grep nosuid
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /tmp | grep nosuid
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
