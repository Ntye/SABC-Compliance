control 'JR2.C.6.2.8' do
  title 'Ensure no duplicate group names exist.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_8'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      
      cut -d: -f1 /etc/group | sort | uniq -d | while read -r x; do
       echo "Duplicate group name $x in /etc/group"
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
      
      cut -d: -f1 /etc/group | sort | uniq -d | while read -r x; do
       echo "Duplicate group name $x in /etc/group"
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
