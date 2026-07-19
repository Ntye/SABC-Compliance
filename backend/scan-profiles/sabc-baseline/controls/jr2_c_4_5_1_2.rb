control 'JR2.C.4.5.1.2' do
  title 'Ensure password expiration is 365 days or less.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
grep PASS_MAX_DAYS /etc/login.defs
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
v=$(awk '/^\s*PASS_MAX_DAYS\b/ {print $2}' /etc/login.defs)
[ -n "$v" ] || exit 1
[ "$v" -ge 1 ] && [ "$v" -le 365 ] || exit 1
bad=$(awk -F: '($2!~/^[!*]/ && ($5>365 || $5 == "" || $5 == -1)) {print $1}' /etc/shadow)
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
