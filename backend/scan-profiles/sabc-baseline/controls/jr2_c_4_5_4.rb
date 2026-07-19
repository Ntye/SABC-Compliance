control 'JR2.C.4.5.4' do
  title 'Ensure maximum number of same consecutive characters in a password is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_4'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
v=$(grep -Ehs '^[[:space:]]*maxrepeat[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
[ -n "$v" ] && [ "$v" -ge 1 ] && [ "$v" -le 3 ] && exit 0
exit 1
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
rpm -q libpwquality >/dev/null 2>&1 || exit 1
v=$(awk -F= '/^\s*maxrepeat\s*=/ {gsub(/ /,"",$2); print $2}' \
    /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -n1)
[ -n "$v" ] || exit 1
[ "$v" -ge 1 ] && [ "$v" -le 3 ]
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
