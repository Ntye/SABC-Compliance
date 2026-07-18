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
#!/usr/bin/env bash
installed=0
for p in dovecot cyrus-imapd; do rpm -q "$p" >/dev/null 2>&1 && installed=1; done
[ "$installed" -eq 0 ] && exit 0
# Package present (may be a dependency): its units must be neither enabled nor active.
systemctl is-enabled dovecot.socket dovecot.service cyrus-imapd.service 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active dovecot.socket dovecot.service cyrus-imapd.service 2>/dev/null | grep -q '^active' && exit 1
exit 0
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
