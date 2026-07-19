control 'JR2.C.1.3.3' do
  title 'Ensure authentication required for single user mode.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_3_3'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
grep -Eq '^root:\$[0-9]' /etc/shadow || echo "root is locked"
SABC_BASH_EOF
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
exec /bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
grep -Eq 'sulogin' /usr/lib/systemd/system/rescue.service /etc/systemd/system/rescue.service.d/*.conf 2>/dev/null || exit 1
grep -Eq 'sulogin' /usr/lib/systemd/system/emergency.service /etc/systemd/system/emergency.service.d/*.conf 2>/dev/null || exit 1
exit 0
SABC_BASH_EOF
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
