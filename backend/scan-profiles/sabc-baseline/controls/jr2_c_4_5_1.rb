control 'JR2.C.4.5.1' do
  title 'Ensure default group for the root account is GID 0.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      grep "^root:" /etc/passwd | cut -f4 -d:
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
      grep "^root:" /etc/passwd | cut -f4 -d:
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
