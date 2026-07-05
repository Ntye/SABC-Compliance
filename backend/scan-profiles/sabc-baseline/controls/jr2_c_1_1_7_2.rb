control 'JR2.C.1.1.7.2' do
  title 'Ensure nosuid option set on /home partition.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_1_7_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /home | grep -v 'nosuid'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /home | grep -v 'nosuid'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
