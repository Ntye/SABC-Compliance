control 'JR2.C.4.5.1.6' do
  title 'Ensure the number of changed characters in a new password is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1_6'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -P '^\h*difok\h*=\h*([2-9]|[1-9][0-9]+)\b' /etc/security/pwquality.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -P '^\h*difok\h*=\h*([2-9]|[1-9][0-9]+)\b' /etc/security/pwquality.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
