control 'JR2.C.5.1.2.4' do
  title 'Ensure rsyslog is not configured to receive logs from a remote client.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_2_4'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep '$ModLoad imtcp' /etc/rsyslog.conf /etc/rsyslog.d/*.conf
      grep '$InputTCPServerRun' /etc/rsyslog.conf /etc/rsyslog.d/*.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep '$ModLoad imtcp' /etc/rsyslog.conf /etc/rsyslog.d/*.conf
      grep '$InputTCPServerRun' /etc/rsyslog.conf /etc/rsyslog.d/*.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
