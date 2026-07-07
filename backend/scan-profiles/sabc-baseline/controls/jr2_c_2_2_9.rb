control 'JR2.C.2.2.9' do
  title 'Ensure IMAP and POP3 server are not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_9'
  if os[:family] == 'debian'
    describe package('dovecot-imapd') do
      it { should_not be_installed }
    end
    describe package('dovecot-pop3d') do
      it { should_not be_installed }
    end
  end
  if os[:family] == 'redhat'
    describe package('dovecot-imapd') do
      it { should_not be_installed }
    end
    describe package('dovecot-pop3d') do
      it { should_not be_installed }
    end
  end
end
