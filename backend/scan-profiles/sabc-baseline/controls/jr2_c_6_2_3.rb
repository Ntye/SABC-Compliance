control 'JR2.C.6.2.3' do
  title 'Ensure all groups in /etc/passwd exist in /etc/group .'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_3'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      
      for i in $(cut -s -d: -f4 /etc/passwd | sort -u ); do
       grep -q -P "^.*?:[^:]*:$i:" /etc/group
       if [ $? -ne 0 ]; then
       echo "Group $i is referenced by /etc/passwd but does not exist in /etc/group"
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
      
      for i in $(cut -s -d: -f4 /etc/passwd | sort -u ); do
       grep -q -P "^.*?:[^:]*:$i:" /etc/group
       if [ $? -ne 0 ]; then
       echo "Group $i is referenced by /etc/passwd but does not exist in /etc/group"
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
