control 'JR2.C.3.4.1.4' do
  title 'Ensure ufw loopback traffic is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_1_4'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      ufw status verbose
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      firewall-cmd --get-zone-of-interface=lo
      firewall-cmd --list-all --zone=trusted
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
