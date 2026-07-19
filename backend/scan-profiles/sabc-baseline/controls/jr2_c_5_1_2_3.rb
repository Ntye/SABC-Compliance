control 'JR2.C.5.1.2.3' do
  title 'Ensure rsyslog default file permissions are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_2_3'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
grep ^\$FileCreateMode /etc/rsyslog.conf /etc/rsyslog.d/*.conf
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
rpm -q rsyslog >/dev/null 2>&1 || exit 101
m=$(grep -Ersh '^\$FileCreateMode\s+[0-7]+' /etc/rsyslog.conf /etc/rsyslog.d 2>/dev/null | awk '{print $2}' | tail -n1)
[ -n "$m" ] || exit 1
[ $(( 8#$m & 8#0137 )) -eq 0 ]
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
