control 'JR2.C.6.1.10' do
  title 'Ensure permissions on /etc/opasswd are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_1_10'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      [ -e "/etc/security/opasswd" ] && stat -Lc "%n %a %u/%U %g/%G" /etc/security/opasswd
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      [ -e "/etc/security/opasswd" ] && stat -Lc "%n %a %u/%U %g/%G" /etc/security/opasswd
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
