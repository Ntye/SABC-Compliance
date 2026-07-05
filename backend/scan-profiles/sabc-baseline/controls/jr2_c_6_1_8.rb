control 'JR2.C.6.1.8' do
  title 'Ensure permissions on /etc/gshadow- are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_1_8'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      stat -Lc "%n %a %u/%U %g/%G" /etc/gshadow-
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      stat -Lc "%n %a %u/%U %g/%G" /etc/gshadow-
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
