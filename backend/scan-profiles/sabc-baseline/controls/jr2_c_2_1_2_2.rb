control 'JR2.C.2.1.2.2' do
  title 'Ensure chrony is enabled and running.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_1_2_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled chrony.service
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled chrony.service
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
