control 'JR2.C.2.2.1' do
  title 'Ensure Avahi Server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_1'
  if os.debian?
    describe package('avahi-daemon') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
      rpm -q avahi
      systemctl is-enabled avahi-daemon.socket avahi-daemon.service 2>/dev/null |
      systemctl is-active avahi-daemon.socket avahi-daemon.service 2>/dev/null |
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
