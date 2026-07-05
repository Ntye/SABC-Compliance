control 'JR2.C.1.1.4.1' do
  title 'Ensure nodev option set on /var/tmp partition.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_1_4_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /var/tmp | grep -v 'nodev'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /var/tmp | grep -v 'nodev'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
