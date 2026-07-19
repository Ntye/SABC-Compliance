control 'JR2.C.6.1.4' do
  title 'Ensure permissions on /etc/group- are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_1_4'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
stat -Lc "%n %a %u/%U %g/%G" /etc/group-
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
f=/etc/group-
[ -e "$f" ] || exit 0
set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
[ "$o" = "root" ] || exit 1
{ [ "$g" = "root" ]; } || exit 1
[ $(( 8#$m & ~8#644 & 8#7777 )) -eq 0 ] || exit 1
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
