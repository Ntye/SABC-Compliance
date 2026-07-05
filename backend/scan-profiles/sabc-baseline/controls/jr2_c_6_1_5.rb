control 'JR2.C.6.1.5' do
  title 'Ensure permissions on /etc/shadow are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_1_5'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      stat -Lc "%n %a %u/%U %g/%G" /etc/shadow
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      stat -Lc "%n %a %u/%U %g/%G" /etc/shadow
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
