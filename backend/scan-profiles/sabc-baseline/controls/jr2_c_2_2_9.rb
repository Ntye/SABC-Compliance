control 'JR2.C.2.2.9' do
  title 'Ensure IMAP and POP3 server are not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_9'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' dovecot-imapd dovecot-pop3d
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      rpm -q dovecot-imapd dovecot-pop3d
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
