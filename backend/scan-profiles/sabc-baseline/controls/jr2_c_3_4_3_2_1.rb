control 'JR2.C.3.4.3.2.1' do
  title 'Ensure iptables default deny firewall policy.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_3_2_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      iptables -L -n
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      iptables -L -n
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
