control 'JR2.C.4.5.1.5' do
  title 'Ensure all users last password change date is in the past.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1_5'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      #!/usr/bin/env bash
      
      {
       l_output2=""
       while read -r l_user; do
       l_change="$(chage --list $l_user | awk -F: '($1 ~ /^\s*Last\s+password\s+change/ && $2 !~ /never/){print $2}' | xargs)"
       if [[ "$(date -d "$l_change" +%s)" -gt "$(date +%s)" ]]; then
       l_output2="$l_output2\n - User: \"$l_user\" last password change is in the future \"$l_change\""
       fi
       done < <(awk -F: '($2 ~ /^[^*!xX\n\r][^\n\r]+/){print $1}' /etc/shadow)
       if [ -z "$l_output2" ]; then # If l_output2 is empty, we pass
       echo -e "\n- Audit Result:\n ** PASS **\n - All user password changes are in the past \n"
       else
       echo -e "\n- Audit Result:\n ** FAIL **\n - * Reasons for audit failure * :$l_output2\n"
       fi
      }
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
      #!/usr/bin/env bash
      
      {
       l_output2=""
       while read -r l_user; do
       l_change="$(chage --list $l_user | awk -F: '($1 ~ /^\s*Last\s+password\s+change/ && $2 !~ /never/){print $2}' | xargs)"
       if [[ "$(date -d "$l_change" +%s)" -gt "$(date +%s)" ]]; then
       l_output2="$l_output2\n - User: \"$l_user\" last password change is in the future \"$l_change\""
       fi
       done < <(awk -F: '($2 ~ /^[^*!xX\n\r][^\n\r]+/){print $1}' /etc/shadow)
       if [ -z "$l_output2" ]; then # If l_output2 is empty, we pass
       echo -e "\n- Audit Result:\n ** PASS **\n - All user password changes are in the past \n"
       else
       echo -e "\n- Audit Result:\n ** FAIL **\n - * Reasons for audit failure * :$l_output2\n"
       fi
      }
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
