control 'JR2.C.6.2.3' do
  title 'Ensure all groups in /etc/passwd exist in /etc/group .'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash
      
      for i in $(cut -s -d: -f4 /etc/passwd | sort -u ); do
       grep -q -P "^.*?:[^:]*:$i:" /etc/group
       if [ $? -ne 0 ]; then
       echo "Group $i is referenced by /etc/passwd but does not exist in /etc/group"
       fi
      done
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash
      
      for i in $(cut -s -d: -f4 /etc/passwd | sort -u ); do
       grep -q -P "^.*?:[^:]*:$i:" /etc/group
       if [ $? -ne 0 ]; then
       echo "Group $i is referenced by /etc/passwd but does not exist in /etc/group"
       fi
      done
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
