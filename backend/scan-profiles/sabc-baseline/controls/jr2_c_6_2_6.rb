control 'JR2.C.6.2.6' do
  title 'Ensure no duplicate GIDs exist.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_6'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
#!/bin/bash 

cut -d: -f3 /etc/group | sort | uniq -d | while read x ; do
 echo "Duplicate GID ($x) in /etc/group"
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
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
#!/usr/bin/env bash
cut -d: -f4 /etc/group | sort | uniq -d | grep -q . && exit 1
exit 0
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
