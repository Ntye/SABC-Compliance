control 'JR2.C.4.4.2' do
  title 'Ensure lockout for failed password attempts is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_4_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
d=$(grep -Ehs '^[[:space:]]*deny[[:space:]]*=' /etc/security/faillock.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
[ -n "$d" ] && [ "$d" -ge 1 ] && [ "$d" -le 5 ] || exit 1
u=$(grep -Ehs '^[[:space:]]*unlock_time[[:space:]]*=' /etc/security/faillock.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
[ -n "$u" ] || exit 1
[ "$u" -eq 0 ] || [ "$u" -ge 900 ] || exit 1
grep -qs 'pam_faillock.so' /etc/pam.d/common-auth || exit 1
exit 0
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
d=$(awk -F= '/^\s*deny\s*=/ {gsub(/ /,"",$2); print $2}' /etc/security/faillock.conf 2>/dev/null | tail -n1)
u=$(awk -F= '/^\s*unlock_time\s*=/ {gsub(/ /,"",$2); print $2}' /etc/security/faillock.conf 2>/dev/null | tail -n1)
[ -n "$d" ] && [ "$d" -ge 1 ] && [ "$d" -le 5 ] || exit 1
[ -n "$u" ] && { [ "$u" -eq 0 ] || [ "$u" -ge 900 ]; } || exit 1
grep -Eq 'pam_faillock\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth || exit 1
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
