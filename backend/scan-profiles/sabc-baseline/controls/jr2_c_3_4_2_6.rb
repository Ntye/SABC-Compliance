control 'JR2.C.3.4.2.6' do
  title 'Ensure nftables default deny firewall policy.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_2_6'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      nft list ruleset | grep 'hook input'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      nft list ruleset | grep 'hook input'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
