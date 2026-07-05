control 'JR2.C.3.4.3.2.2' do
  title 'Ensure iptables loopback traffic is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_3_2_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      iptables -L INPUT -v -n
      iptables -L OUTPUT -v -n
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      iptables -L INPUT -v -n
      iptables -L OUTPUT -v -n
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
