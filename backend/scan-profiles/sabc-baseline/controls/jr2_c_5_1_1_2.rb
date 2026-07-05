control 'JR2.C.5.1.1.2' do
  title 'Ensure journald is configured to compress large log files.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_1_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Psi '^\h*Compress\h*=\h*yes\b' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Psi '^\h*Compress\h*=\h*yes\b' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
