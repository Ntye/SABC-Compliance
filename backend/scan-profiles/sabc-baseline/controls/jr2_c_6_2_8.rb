control 'JR2.C.6.2.8' do
  title 'Ensure no duplicate group names exist.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_8'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash
      
      cut -d: -f1 /etc/group | sort | uniq -d | while read -r x; do
       echo "Duplicate group name $x in /etc/group"
      done
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash
      
      cut -d: -f1 /etc/group | sort | uniq -d | while read -r x; do
       echo "Duplicate group name $x in /etc/group"
      done
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
