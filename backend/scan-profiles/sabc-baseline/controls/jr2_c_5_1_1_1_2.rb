control 'JR2.C.5.1.1.1.2' do
  title 'Ensure journald is not configured to receive logs from a remote client.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_1_1_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled systemd-journal-remote.socket
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-enabled systemd-journal-remote.socket
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
