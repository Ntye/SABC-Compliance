control 'JR2.C.6.2.7' do
  title 'Ensure no duplicate user names exist.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_7'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash
      
      cut -d: -f1 /etc/passwd | sort | uniq -d | while read -r x; do
       echo "Duplicate login name $x in /etc/passwd"
      done
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash
      
      cut -d: -f1 /etc/passwd | sort | uniq -d | while read -r x; do
       echo "Duplicate login name $x in /etc/passwd"
      done
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
