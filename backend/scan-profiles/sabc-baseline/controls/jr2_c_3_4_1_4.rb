control 'JR2.C.3.4.1.4' do
  title 'Ensure ufw loopback traffic is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_1_4'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      ufw status verbose
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
      firewall-cmd --get-zone-of-interface=lo
      firewall-cmd --list-all --zone=trusted
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
