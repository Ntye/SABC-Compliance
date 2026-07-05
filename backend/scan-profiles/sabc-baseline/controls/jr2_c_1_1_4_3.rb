control 'JR2.C.1.1.4.3' do
  title 'Ensure nosuid option set on /var/tmp partition.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_1_4_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /var/tmp | grep -v 'nosuid'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /var/tmp | grep -v 'nosuid'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
