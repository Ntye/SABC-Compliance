control 'JR2.C.3.4.1.2' do
  title 'Ensure iptables-persistent is not installed with ufw.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_1_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -s iptables-persistent
      package 'iptables-persistent' is not installed and no information is available
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -s iptables-persistent
      package 'iptables-persistent' is not installed and no information is available
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
