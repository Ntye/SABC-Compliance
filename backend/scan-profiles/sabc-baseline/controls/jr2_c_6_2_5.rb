control 'JR2.C.6.2.5' do
  title 'Ensure no duplicate UIDs exist.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_5'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
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
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
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
      its('exit_status') { should cmp 0 }
    end
  end
end
