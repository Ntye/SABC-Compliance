control 'JR2.C.4.5.2' do
  title 'Ensure default user umask is 027 or more restrictive.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
grep -Eqs '^[[:space:]]*UMASK[[:space:]]+027' /etc/login.defs || exit 1
grep -Eqs '^[[:space:]]*umask[[:space:]]+027' /etc/profile.d/*.sh /etc/profile 2>/dev/null || exit 1
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
u=$(awk '/^\s*UMASK\s/ {print $2}' /etc/login.defs | tail -n1)
case "$u" in 027|077) : ;; *) exit 1 ;; esac
grep -Ersq '^\s*umask\s+0?(0[0-2][0-7]|[0-2][0-7])\b' /etc/profile /etc/profile.d /etc/bashrc 2>/dev/null && exit 1
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
