control 'JR2.C.4.1.5' do
  title 'Ensure permissions on /etc/cron.weekly are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_1_5'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      stat -Lc 'Access: (%a/%A) Uid: ( %u/ %U) Gid: ( %g/ %G)' /etc/cron.weekly/
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      stat -Lc 'Access: (%a/%A) Uid: ( %u/ %U) Gid: ( %g/ %G)' /etc/cron.weekly/
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
