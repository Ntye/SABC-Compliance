control 'JR2.C.1.7.9' do
  title 'Ensure XDCMP is not enabled.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_7_9'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Eis '^\s*Enable\s*=\s*true' /etc/gdm3/custom.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Eis '^\s*Enable\s*=\s*true' /etc/gdm3/custom.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
