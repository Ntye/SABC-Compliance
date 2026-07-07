control 'JR2.C.3.4.3.3.1' do
  title 'Ensure ip6tables default deny firewall policy.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_3_3_1'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      ip6tables -L -n
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
      ip6tables -L -n
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
