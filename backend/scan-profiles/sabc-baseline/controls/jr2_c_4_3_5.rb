control 'JR2.C.4.3.5' do
  title 'Ensure sudo authentication timeout is configured correctly.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_3_5'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -roP "timestamp_timeout=\K[0-9]*" /etc/sudoers*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -roP "timestamp_timeout=\K[0-9]*" /etc/sudoers*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
