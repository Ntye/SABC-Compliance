control 'JR2.C.6.2.6' do
  title 'Ensure no duplicate GIDs exist.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_6'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash 
      
      cut -d: -f3 /etc/group | sort | uniq -d | while read x ; do
       echo "Duplicate GID ($x) in /etc/group"
      done
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash 
      
      cut -d: -f3 /etc/group | sort | uniq -d | while read x ; do
       echo "Duplicate GID ($x) in /etc/group"
      done
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
