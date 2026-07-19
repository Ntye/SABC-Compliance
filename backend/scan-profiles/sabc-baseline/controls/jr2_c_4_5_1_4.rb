control 'JR2.C.4.5.1.4' do
  title 'Ensure inactive password lock is 30 days or less.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1_4'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
useradd -D | grep INACTIVE
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
d=$(useradd -D | awk -F= '/INACTIVE/{print $2}')
[ -n "$d" ] && [ "$d" -ge 0 ] && [ "$d" -le 30 ] || exit 1
bad=$(awk -F: '($2!~/^[!*]/ && ($7 == "" || $7 > 30 || $7 < 0)) {print $1}' /etc/shadow)
[ -z "$bad" ]
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
