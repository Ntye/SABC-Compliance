control 'JR2.C.3.4.1.3' do
  title 'Ensure ufw service is enabled.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_1_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled ufw.service
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled firewalld
      systemctl is-active firewalld
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
