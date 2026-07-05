control 'JR2.C.1.3.3' do
  title 'Ensure authentication required for single user mode.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_3_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Eq '^root:\$[0-9]' /etc/shadow || echo "root is locked"
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Eq '^root:\$[0-9]' /etc/shadow || echo "root is locked"
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
