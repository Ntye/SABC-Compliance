control 'JR2.C.1.6.6' do
  title 'Ensure permissions on /etc/issue.net are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_6_6'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      stat -Lc 'Access: (%#a/%A) Uid: ( %u/ %U) Gid: { %g/ %G)' /etc/issue.net
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      stat -Lc 'Access: (%#a/%A) Uid: ( %u/ %U) Gid: { %g/ %G)' /etc/issue.net
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
