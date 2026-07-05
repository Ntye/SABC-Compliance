control 'JR2.C.2.1.3.1' do
  title 'Ensure systemd-timesyncd configured with authorized timeserver.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_1_3_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Ph '^\h*(NTP|FallbackNTP)=\H+' /etc/systemd/timesyncd.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Ph '^\h*(NTP|FallbackNTP)=\H+' /etc/systemd/timesyncd.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
