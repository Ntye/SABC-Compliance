control 'JR2.C.5.1.2.3' do
  title 'Ensure rsyslog default file permissions are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_2_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep ^\$FileCreateMode /etc/rsyslog.conf /etc/rsyslog.d/*.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep ^\$FileCreateMode /etc/rsyslog.conf /etc/rsyslog.d/*.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
