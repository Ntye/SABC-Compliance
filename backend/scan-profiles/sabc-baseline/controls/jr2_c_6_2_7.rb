control 'JR2.C.6.2.7' do
  title 'Ensure no duplicate user names exist.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_7'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
#!/bin/bash

cut -d: -f1 /etc/passwd | sort | uniq -d | while read -r x; do
 echo "Duplicate login name $x in /etc/passwd"
done
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
cut -d: -f1 /etc/passwd | sort | uniq -d | grep -q . && exit 1
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
