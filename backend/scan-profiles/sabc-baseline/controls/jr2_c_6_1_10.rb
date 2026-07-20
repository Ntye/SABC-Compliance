control 'JR2.C.6.1.10' do
  title 'Ensure permissions on /etc/opasswd are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_1_10'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
for f in /etc/security/opasswd /etc/security/opasswd.old; do
  [ -e "$f" ] || continue
  [ "$(stat -c '%a %U %G' "$f")" = "600 root root" ] || exit 1
done
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
/bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
for f in /etc/security/opasswd /etc/security/opasswd.old; do
  [ -e "$f" ] || continue
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ "$o" = root ] && [ "$g" = root ] || exit 1
  [ $(( 8#$m & 8#0177 )) -eq 0 ] || exit 1
done
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
