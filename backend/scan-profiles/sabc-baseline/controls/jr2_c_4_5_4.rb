control 'JR2.C.4.5.4' do
  title 'Ensure maximum number of same consecutive characters in a password is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_4'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Pi '^\h*maxrepeat\h*=\h*[1-3]\b' /etc/security/pwquality.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Pi '^\h*maxrepeat\h*=\h*[1-3]\b' /etc/security/pwquality.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
