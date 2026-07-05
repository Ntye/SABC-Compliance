control 'JR2.C.3.4.2.3' do
  title 'Ensure a nftables table exists.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_2_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      nft list tables
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      nft list tables
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
