control 'JR2.C.5.1.2.2' do
  title 'Ensure rsyslog service is enabled.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_2_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
systemctl is-enabled rsyslog
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
/bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
rpm -q rsyslog >/dev/null 2>&1 || exit 101
systemctl is-enabled rsyslog.service 2>/dev/null | grep -q enabled || exit 1
systemctl is-active rsyslog.service 2>/dev/null | grep -q '^active' || exit 1
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
