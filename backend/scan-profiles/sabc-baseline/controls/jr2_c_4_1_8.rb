control 'JR2.C.4.1.8' do
  title 'Ensure cron is restricted to authorized users.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_1_8'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash

{
 l_output="" l_output2=""
 if dpkg-query -W cron > /dev/null 2>&1; then
 l_file="/etc/cron.allow"
 [ -e /etc/cron.deny ] && l_output2="$l_output2\n - cron.deny exists"
 if [ ! -e /etc/cron.allow ]; then 
 l_output2="$l_output2\n - cron.allow doesn't exist"
 else
 l_mask='0137'
 l_maxperm="$( printf '%o' $(( 0777 & ~$l_mask)) )"
 while read l_mode l_fown l_fgroup; do 
 if [ $(( $l_mode & $l_mask )) -gt 0 ]; then
 l_output2="$l_output2\n - \"$l_file\" is mode: \"$l_mode\" (should be mode: \"$l_maxperm\" or more restrictive)"
 else
 l_output="$l_output\n - \"$l_file\" is correctly set to mode: \"$l_mode\""
 fi
 if [ "$l_fown" != "root" ]; then
 l_output2="$l_output2\n - \"$l_file\" is owned by user \"$l_fown\" (should be owned by \"root\")"
 else
 l_output="$l_output\n - \"$l_file\" is correctly owned by user: \"$l_fown\""
 fi
 if [ "$l_fgroup" != "crontab" ]; then
 l_output2="$l_output2\n - \"$l_file\" is owned by group: \"$l_fgroup\" (should be owned by group: \"crontab\")"
 else
 l_output="$l_output\n - \"$l_file\" is correctly owned by group: \"$l_fgroup\""
 fi
 done < <(stat -Lc '%#a %U %G' "$l_file")
 fi
 else
 l_output="$l_output\n - cron is not installed on the system"
 fi
 if [ -z "$l_output2" ]; then
 echo -e "\n- Audit Result:\n ** PASS **$l_output\n"
 else
 echo -e "\n- Audit Result:\n ** FAIL **\n - Reason(s) for audit failure:$l_output2\n"
 fi
}
SABC_BASH_EOF
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
/bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
rpm -q cronie >/dev/null 2>&1 || exit 101
[ -f /etc/cron.allow ] || exit 1
set -- $(stat -Lc '%a %U %G' /etc/cron.allow)
m=$1 o=$2 g=$3
[ "$o" = root ] && [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
if [ -f /etc/cron.deny ]; then
  set -- $(stat -Lc '%a %U %G' /etc/cron.deny)
  m=$1 o=$2 g=$3
  [ "$o" = root ] && [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
fi
exit 0
SABC_BASH_EOF
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
