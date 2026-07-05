control 'JR2.C.3.4.2.7' do
  title 'Ensure nftables service is enabled.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_2_7'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled nftables
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled nftables
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
