control 'JR2.C.3.4.2.1' do
  title 'Ensure nftables is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_2_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -s nftables | grep 'Status: install ok installed'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -s nftables | grep 'Status: install ok installed'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
