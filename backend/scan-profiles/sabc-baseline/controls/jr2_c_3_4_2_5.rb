control 'JR2.C.3.4.2.5' do
  title 'Ensure nftables loopback traffic is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_2_5'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      nft list ruleset | awk '/hook input/,/}/' | grep 'iif "lo" accept'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      nft list ruleset | awk '/hook input/,/}/' | grep 'iif "lo" accept'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
