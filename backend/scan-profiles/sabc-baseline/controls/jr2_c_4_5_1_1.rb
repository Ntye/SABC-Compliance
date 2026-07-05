control 'JR2.C.4.5.1.1' do
  title 'Ensure minimum days between password changes is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep PASS_MIN_DAYS /etc/login.defs
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep PASS_MIN_DAYS /etc/login.defs
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
