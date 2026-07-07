control 'JR2.C.4.2.4' do
  title 'Ensure SSH access is limited.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_2_4'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      if command -v sshd >/dev/null 2>&1; then
        sshd -T 2>/dev/null | grep -Eqi '^(allowusers|allowgroups|denyusers|denygroups)[[:space:]]+[^[:space:]]' && exit 0
      fi
      cat /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | grep -Eqi '^[[:space:]]*(Allow|Deny)(Users|Groups)[[:space:]]+[^[:space:]]' && exit 0
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
      if command -v sshd >/dev/null 2>&1; then
        sshd -T 2>/dev/null | grep -Eqi '^(allowusers|allowgroups|denyusers|denygroups)[[:space:]]+[^[:space:]]' && exit 0
      fi
      cat /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | grep -Eqi '^[[:space:]]*(Allow|Deny)(Users|Groups)[[:space:]]+[^[:space:]]' && exit 0
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
