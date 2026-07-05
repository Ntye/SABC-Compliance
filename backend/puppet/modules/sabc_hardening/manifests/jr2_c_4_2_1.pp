# JR2.C.4.2.1 (CIS Level 1) — Ensure permissions on /etc/ssh/sshd_config are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_2_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_2_1_debian':
      command  => @(SABC_CMD/L),
        #!/usr/bin/env bash
        
        {
         chmod u-x,og-rwx /etc/ssh/sshd_config
         chown root:root /etc/ssh/sshd_config
         while IFS= read -r -d $'\0' l_file; do
         if [ -e "$l_file" ]; then
         chmod u-x,og-rwx "$l_file"
         chown root:root "$l_file"
         fi
         done < <(find /etc/ssh/sshd_config.d -type f -print0)
        }
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         l_output="" l_output2=""
         unset a_sshdfiles && a_sshdfiles=()
         [ -e "/etc/ssh/sshd_config" ] && a_sshdfiles+=("$(stat -Lc '%n^%#a^%U^%G' "/etc/ssh/sshd_config")")
         while IFS= read -r -d $'\0' l_file; do
         [ -e "$l_file" ] && a_sshdfiles+=("$(stat -Lc '%n^%#a^%U^%G' "$l_file")")
         done < <(find /etc/ssh/sshd_config.d -type f \( -perm /077 -o ! -user root -o ! -group root \) -print0)
         if (( ${#a_sshdfiles[@]} != 0 )); then
         perm_mask='0177'
         maxperm="$( printf '%o' $(( 0777 & ~$perm_mask)) )"
         while IFS="^" read -r l_file l_mode l_user l_group; do
         l_out2=""
         [ $(( $l_mode & $perm_mask )) -gt 0 ] && l_out2="$l_out2\n - Is mode: \"$l_mode\" should be: \"$maxperm\" or more restrictive"
         [ "$l_user" != "root" ] && l_out2="$l_out2\n - Is owned by \"$l_user\" should be owned by \"root\""
         [ "$l_group" != "root" ] && l_out2="$l_out2\n - Is group owned by \"$l_user\" should be group owned by \"root\""
         if [ -n "$l_out2" ]; then
         l_output2="$l_output2\n - File: \"$l_file\":$l_out2"
         else
         l_output="$l_output\n - File: \"$l_file\":\n - Correct: mode ($l_mode), owner ($l_user), and group owner ($l_group) configured"
         fi
         done <<< "$(printf '%s\n' "${a_sshdfiles[@]}")"
         fi
         unset a_sshdfiles
         # If l_output2 is empty, we pass
         if [ -z "$l_output2" ]; then
         echo -e "\n- Audit Result:\n *** PASS ***\n- * Correctly set * :\n$l_output\n"
         else
         echo -e "\n- Audit Result:\n ** FAIL **\n - * Reasons for audit failure * :\n$l_output2\n"
         [ -n "$l_output" ] && echo -e " - * Correctly set * :\n$l_output\n"
         fi
        }
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_2_1_redhat':
      command  => @(SABC_CMD/L),
        #!/usr/bin/env bash
        
        {
         chmod u-x,og-rwx /etc/ssh/sshd_config
         chown root:root /etc/ssh/sshd_config
         while IFS= read -r -d $'\0' l_file; do
         if [ -e "$l_file" ]; then
         chmod u-x,og-rwx "$l_file"
         chown root:root "$l_file"
         fi
         done < <(find /etc/ssh/sshd_config.d -type f -print0)
        }
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         l_output="" l_output2=""
         unset a_sshdfiles && a_sshdfiles=()
         [ -e "/etc/ssh/sshd_config" ] && a_sshdfiles+=("$(stat -Lc '%n^%#a^%U^%G' "/etc/ssh/sshd_config")")
         while IFS= read -r -d $'\0' l_file; do
         [ -e "$l_file" ] && a_sshdfiles+=("$(stat -Lc '%n^%#a^%U^%G' "$l_file")")
         done < <(find /etc/ssh/sshd_config.d -type f \( -perm /077 -o ! -user root -o ! -group root \) -print0)
         if (( ${#a_sshdfiles[@]} != 0 )); then
         perm_mask='0177'
         maxperm="$( printf '%o' $(( 0777 & ~$perm_mask)) )"
         while IFS="^" read -r l_file l_mode l_user l_group; do
         l_out2=""
         [ $(( $l_mode & $perm_mask )) -gt 0 ] && l_out2="$l_out2\n - Is mode: \"$l_mode\" should be: \"$maxperm\" or more restrictive"
         [ "$l_user" != "root" ] && l_out2="$l_out2\n - Is owned by \"$l_user\" should be owned by \"root\""
         [ "$l_group" != "root" ] && l_out2="$l_out2\n - Is group owned by \"$l_user\" should be group owned by \"root\""
         if [ -n "$l_out2" ]; then
         l_output2="$l_output2\n - File: \"$l_file\":$l_out2"
         else
         l_output="$l_output\n - File: \"$l_file\":\n - Correct: mode ($l_mode), owner ($l_user), and group owner ($l_group) configured"
         fi
         done <<< "$(printf '%s\n' "${a_sshdfiles[@]}")"
         fi
         unset a_sshdfiles
         # If l_output2 is empty, we pass
         if [ -z "$l_output2" ]; then
         echo -e "\n- Audit Result:\n *** PASS ***\n- * Correctly set * :\n$l_output\n"
         else
         echo -e "\n- Audit Result:\n ** FAIL **\n - * Reasons for audit failure * :\n$l_output2\n"
         [ -n "$l_output" ] && echo -e " - * Correctly set * :\n$l_output\n"
         fi
        }
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
