# JR2.C.4.1.8 (CIS Level 1) — Ensure cron is restricted to authorized users.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_1_8 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_1_8_debian':
      command  => @(SABC_CMD/L),
        #!/usr/bin/env bash
        
        {
         if dpkg-query -W cron > /dev/null 2> then
         l_file="/etc/cron.allow"
         l_mask='0137'
         l_maxperm="$( printf '%o' $(( 0777 & ~$l_mask)) )"
         if [ -e /etc/cron.deny ]; then
         echo -e " - Removing \"/etc/cron.deny\""
         rm -f /etc/cron.deny
         fi
         if [ ! -e /etc/cron.allow ]; then
         echo -e " - creating \"$l_file\""
         touch "$l_file"
         fi
         while read l_mode l_fown l_fgroup; do
         if [ $(( $l_mode & $l_mask )) -gt 0 ]; then
         echo -e " - Removing excessive permissions from \"$l_file\""
         chmod u-x,g-wx,o-rwx "$l_file"
         fi
         if [ "$l_fown" != "root" ]; then
         echo -e " - Changing owner on \"$l_file\" from: \"$l_fown\" to: \"root\""
         chown root "$l_file"
         fi
         if [ "$l_fgroup" != "crontab" ]; then
         echo -e " - Changing group owner on \"$l_file\" from: \"$l_fgroup\" to: \"crontab\""
         chgrp crontab "$l_file"
         fi
         done < <(stat -Lc '%#a %U %G' "$l_file")
         else
         echo -e "- cron is not installed on the system, no remediation required\n"
         fi
        }
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         l_output="" l_output2=""
         if dpkg-query -W cron > /dev/null 2> then
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
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_1_8_redhat':
      command  => @(SABC_CMD/L),
        #!/usr/bin/env bash
        
        {
         if rpm -q cron > /dev/null 2> then
         l_file="/etc/cron.allow"
         l_mask='0137'
         l_maxperm="$( printf '%o' $(( 0777 & ~$l_mask)) )"
         if [ -e /etc/cron.deny ]; then
         echo -e " - Removing \"/etc/cron.deny\""
         rm -f /etc/cron.deny
         fi
         if [ ! -e /etc/cron.allow ]; then
         echo -e " - creating \"$l_file\""
         touch "$l_file"
         fi
         while read l_mode l_fown l_fgroup; do
         if [ $(( $l_mode & $l_mask )) -gt 0 ]; then
         echo -e " - Removing excessive permissions from \"$l_file\""
         chmod u-x,g-wx,o-rwx "$l_file"
         fi
         if [ "$l_fown" != "root" ]; then
         echo -e " - Changing owner on \"$l_file\" from: \"$l_fown\" to: \"root\""
         chown root "$l_file"
         fi
         if [ "$l_fgroup" != "crontab" ]; then
         echo -e " - Changing group owner on \"$l_file\" from: \"$l_fgroup\" to: \"crontab\""
         chgrp crontab "$l_file"
         fi
         done < <(stat -Lc '%#a %U %G' "$l_file")
         else
         echo -e "- cron is not installed on the system, no remediation required\n"
         fi
        }
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         l_output="" l_output2=""
         if rpm -q cron > /dev/null 2> then
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
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
