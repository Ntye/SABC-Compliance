control 'JR2.C.1.1.7.2' do
  title 'Ensure nosuid option set on /home partition.'
  impact 0.7
  tag cis_level: 2
  tag control_key: 'jr2_c_1_1_7_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      findmnt -kn /home | grep -v 'nosuid'
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
      findmnt -kn /home | grep -v 'nosuid'
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
