control 'JR2.C.1.4.4' do
  title 'Ensure Automatic Error Reporting is not enabled.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_4_4'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -s apport > /dev/null 2>&1 && grep -Psi -- '^\h*enabled\h*=\h*[^0]\b' /etc/default/apport
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -s apport > /dev/null 2>&1 && grep -Psi -- '^\h*enabled\h*=\h*[^0]\b' /etc/default/apport
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
