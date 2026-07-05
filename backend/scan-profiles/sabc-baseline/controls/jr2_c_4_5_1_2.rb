control 'JR2.C.4.5.1.2' do
  title 'Ensure password expiration is 365 days or less.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep PASS_MAX_DAYS /etc/login.defs
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep PASS_MAX_DAYS /etc/login.defs
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
