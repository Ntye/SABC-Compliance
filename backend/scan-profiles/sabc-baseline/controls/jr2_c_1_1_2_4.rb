control 'JR2.C.1.1.2.4' do
  title 'Ensure nosuid option set on /tmp partition.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_1_2_4'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      findmnt -kn /tmp | grep nosuid
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
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
      findmnt -kn /tmp | grep nosuid
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
