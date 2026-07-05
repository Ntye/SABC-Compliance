control 'JR2.C.1.1.8.2' do
  title 'Ensure noexec option set on /dev/shm partition.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_1_8_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /dev/shm | grep -v 'noexec'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -kn /dev/shm | grep -v 'noexec'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
