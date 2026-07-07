control 'JR2.C.2.1.4.3' do
  title 'Ensure ntp is enabled and running.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_1_4_3'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      dpkg-query -W ntp >/dev/null 2>&1 || dpkg-query -W ntpsec >/dev/null 2>&1 || exit 101
      for u in ntp ntpsec; do
        if systemctl is-enabled "$u" 2>/dev/null | grep -q '^enabled'; then
          systemctl is-active "$u" 2>/dev/null | grep -qx active && exit 0
        fi
      done
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
      #!/bin/bash
      rpm -q ntp >/dev/null 2>&1 || rpm -q ntpsec >/dev/null 2>&1 || exit 101
      for u in ntp ntpsec; do
        if systemctl is-enabled "$u" 2>/dev/null | grep -q '^enabled'; then
          systemctl is-active "$u" 2>/dev/null | grep -qx active && exit 0
        fi
      done
      exit 1
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
