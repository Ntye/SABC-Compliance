control 'JR2.C.6.2.5' do
  title 'Ensure no duplicate UIDs exist.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_5'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      
      cut -f3 -d":" /etc/passwd | sort -n | uniq -c | while read x ; do
       [ -z "$x" ] && break
       set - $x
       if [ $1 -gt 1 ]; then
       users=$(awk -F: '($3 == n) { print $1 }' n=$2 /etc/passwd | xargs)
       echo "Duplicate UID ($2): $users"
       fi
      done
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
  if os[:family] == 'redhat'
    v_redhat = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      
      cut -f3 -d":" /etc/passwd | sort -n | uniq -c | while read x ; do
       [ -z "$x" ] && break
       set - $x
       if [ $1 -gt 1 ]; then
       users=$(awk -F: '($3 == n) { print $1 }' n=$2 /etc/passwd | xargs)
       echo "Duplicate UID ($2): $users"
       fi
      done
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
