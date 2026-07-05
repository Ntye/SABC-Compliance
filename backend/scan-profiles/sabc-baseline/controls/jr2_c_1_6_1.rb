control 'JR2.C.1.6.1' do
  title 'Ensure message of the day is configured properly.'
  impact 0.7
  tag cis_level: 2
  tag control_key: 'jr2_c_1_6_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Eis "(\\\v|\\\r|\\\m|\\\s|$(grep '^ID=' /etc/os-release | cut -d= -f2 | sed -e 's/"//g'))" /etc/motd
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Eis "(\\\v|\\\r|\\\m|\\\s|$(grep '^ID=' /etc/os-release | cut -d= -f2 | sed -e 's/"//g'))" /etc/motd
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
