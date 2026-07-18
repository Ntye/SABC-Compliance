control 'JR2.C.4.4.3' do
  title 'Ensure password reuse is limited.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_4_3'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
grep -P -- '^\h*password\h+([^#\n\r]+\h+)?(pam_pwhistory\.so|pam_unix\.so)\b' /etc/pam.d/common-password
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
#!/usr/bin/env bash
r=$(awk -F= '/^\s*remember\s*=/ {gsub(/ /,"",$2); print $2}' /etc/security/pwhistory.conf 2>/dev/null | tail -n1)
[ -z "$r" ] && r=$(grep -Eo 'pam_pwhistory\.so[^#]*remember=[0-9]+' /etc/pam.d/system-auth 2>/dev/null | grep -Eo '[0-9]+' | tail -n1)
[ -n "$r" ] && [ "$r" -ge 5 ]
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
