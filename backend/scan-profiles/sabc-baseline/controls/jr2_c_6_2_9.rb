control 'JR2.C.6.2.9' do
  title 'Ensure root PATH Integrity.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_9'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash
      
      RPCV="$(sudo -Hiu root env | grep '^PATH' | cut -d= -f2)"
      echo "$RPCV" | grep -q "::" && echo "root's path contains a empty directory (::)"
      echo "$RPCV" | grep -q ":$" && echo "root's path contains a trailing (:)"
      for x in $(echo "$RPCV" | tr ":" " "); do
       if [ -d "$x" ]; then
       ls -ldH "$x" | awk '$9 == "." {print "PATH contains current working directory (.)"}
       $3 != "root" {print $9, "is not owned by root"}
       substr($1,6,1) != "-" {print $9, "is group writable"}
       substr($1,9,1) != "-" {print $9, "is world writable"}'
       else
       echo "$x is not a directory"
       fi
      done
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash
      
      RPCV="$(sudo -Hiu root env | grep '^PATH' | cut -d= -f2)"
      echo "$RPCV" | grep -q "::" && echo "root's path contains a empty directory (::)"
      echo "$RPCV" | grep -q ":$" && echo "root's path contains a trailing (:)"
      for x in $(echo "$RPCV" | tr ":" " "); do
       if [ -d "$x" ]; then
       ls -ldH "$x" | awk '$9 == "." {print "PATH contains current working directory (.)"}
       $3 != "root" {print $9, "is not owned by root"}
       substr($1,6,1) != "-" {print $9, "is group writable"}
       substr($1,9,1) != "-" {print $9, "is world writable"}'
       else
       echo "$x is not a directory"
       fi
      done
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
