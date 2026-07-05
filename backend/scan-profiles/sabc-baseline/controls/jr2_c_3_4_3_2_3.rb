control 'JR2.C.3.4.3.2.3' do
  title 'Ensure iptables firewall rules exist for all open ports.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_3_2_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      ss -4tuln
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      ss -4tuln
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
