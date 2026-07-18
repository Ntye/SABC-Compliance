control 'JR2.C.2.2.9' do
  title 'Ensure IMAP and POP3 server are not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_9'
  if os.debian?
    describe package('dovecot-imapd') do
      it { should_not be_installed }
    end
    describe package('dovecot-pop3d') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
      rpm -q dovecot cyrus-imapd
      systemctl is-enabled dovecot.socket dovecot.service cyrus-imapd.service
      systemctl is-active dovecot.socket dovecot.service cyrus-imapd.service
    SABC_V
    if v_redhat.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_redhat do
        its('exit_status') { should cmp 0 }
      end
    end
  end
end
