control 'JR2.C.4.3.6' do
  title 'Ensure access to the su command is restricted.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_3_6'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
#!/bin/bash
grep -Eqs '^[[:space:]]*auth[[:space:]]+(required|requisite)[[:space:]]+pam_wheel\.so[[:space:]].*use_uid.*group=' /etc/pam.d/su || exit 1
g=$(grep -Eos 'group=[^[:space:]]+' /etc/pam.d/su | head -1 | cut -d= -f2)
[ -n "$g" ] || exit 1
getent group "$g" >/dev/null 2>&1 || exit 1
[ -z "$(getent group "$g" | cut -d: -f4)" ] || exit 1
exit 0
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
grep -Eq '^\s*auth\s+(required|requisite)\s+pam_wheel\.so\s+([^#]*\s)?use_uid' /etc/pam.d/su
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
