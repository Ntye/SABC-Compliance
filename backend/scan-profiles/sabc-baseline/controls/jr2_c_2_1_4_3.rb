control 'JR2.C.2.1.4.3' do
  title 'Ensure ntp is enabled and running.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_1_4_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled ntp.service
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled ntp.service
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
