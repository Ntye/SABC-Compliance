control 'JR2.C.3.4.1.6' do
  title 'Ensure ufw default deny firewall policy.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_1_6'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      dpkg-query -W ufw >/dev/null 2>&1 || exit 101
      ufw status verbose 2>/dev/null | grep -q 'Status: active' || exit 1
      ufw status verbose 2>/dev/null | grep -Eq 'Default: deny \(incoming\), deny \(outgoing\), (deny|disabled) \(routed\)' && exit 0
      exit 1
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
      firewall-cmd --get-default-zone
      firewall-cmd --permanent --zone=$(firewall-cmd --get-default-zone) --get-target
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
