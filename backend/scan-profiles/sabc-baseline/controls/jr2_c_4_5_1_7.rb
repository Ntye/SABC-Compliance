control 'JR2.C.4.5.1.7' do
  title 'Ensure preventing the use of dictionary words for passwords is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1_7'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      v=$(grep -Ehs '^[[:space:]]*dictcheck[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
      [ -n "$v" ] && [ "$v" -ge 1 ] && exit 0
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
      v=$(grep -Ehs '^[[:space:]]*dictcheck[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
      [ -n "$v" ] && [ "$v" -ge 1 ] && exit 0
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
