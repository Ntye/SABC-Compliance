control 'JR2.C.1.4.4' do
  title 'Ensure Automatic Error Reporting is not enabled.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_4_4'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      dpkg-query -s apport > /dev/null 2>&1 && grep -Psi -- '^\h*enabled\h*=\h*[^0]\b' /etc/default/apport
    SABC_V
    if v_debian.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_debian do
        its('exit_status') { should cmp 0 }
      end
    end
  end
  if os[:family] == 'redhat'
    v_redhat = command(<<-'SABC_V'.chomp)
      dpkg-query -s apport > /dev/null 2>&1 && grep -Psi -- '^\h*enabled\h*=\h*[^0]\b' /etc/default/apport
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
