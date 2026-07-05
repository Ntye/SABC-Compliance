# JR2.C.6.2.11 (CIS Level 1) — Ensure local interactive user home directories are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_6_2_11 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_6_2_11_debian':
      command  => @(SABC_CMD/L),
        #!/usr/bin/env bash
        
        {
         l_output2=""
         l_valid_shells="^($( awk -F\/ '$NF != "nologin" {print}' /etc/shells | sed -rn '/^\//{s,/,\\\\/,g;p}' | paste -s -d '|' - ))$"
         unset a_uarr && a_uarr=() # Clear and initialize array
         while read -r l_epu l_eph; do # Populate array with users and user home location
         a_uarr+=("$l_epu $l_eph")
         done <<< "$(awk -v pat="$l_valid_shells" -F: '$(NF) ~ pat { print $1 " " $(NF-1) }' /etc/passwd)"
         l_asize="${#a_uarr[@]}" # Here if we want to look at number of users before proceeding 
         [ "$l_asize " -gt "10000" ] && echo -e "\n ** INFO **\n - \"$l_asize\" Local interactive users found on the system\n - This may be a long running process\n"
         while read -r l_user l_home; do
         if [ -d "$l_home" ]; then
         l_mask='0027'
         l_max="$( printf '%o' $(( 0777 & ~$l_mask)) )"
         while read -r l_own l_mode; do
         if [ "$l_user" != "$l_own" ]; then
         l_output2="$l_output2\n - User: \"$l_user\" Home \"$l_home\" is owned by: \"$l_own\"\n - changing ownership to: \"$l_user\"\n"
         chown "$l_user" "$l_home"
         fi
         if [ $(( $l_mode & $l_mask )) -gt 0 ]; then
         l_output2="$l_output2\n - User: \"$l_user\" Home \"$l_home\" is mode: \"$l_mode\" should be mode: \"$l_max\" or more restrictive\n - removing excess permissions\n"
         chmod g-w,o-rwx "$l_home"
         fi
         done <<< "$(stat -Lc '%U %#a' "$l_home")"
         else
         l_output2="$l_output2\n - User: \"$l_user\" Home \"$l_home\" Doesn't exist\n - Please create a home in accordance with local site policy"
         fi
         done <<< "$(printf '%s\n' "${a_uarr[@]}")"
         if [ -z "$l_output2" ]; then # If l_output2 is empty, we pass
         echo -e " - No modification needed to local interactive users home directories"
         else
         echo -e "\n$l_output2"
         fi
        }
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         l_output="" l_output2="" l_heout2="" l_hoout2="" l_haout2=""
         l_valid_shells="^($( awk -F\/ '$NF != "nologin" {print}' /etc/shells | sed -rn '/^\//{s,/,\\\\/,g;p}' | paste -s -d '|' - ))$"
         unset a_uarr && a_uarr=() # Clear and initialize array
         while read -r l_epu l_eph; do # Populate array with users and user home location
         a_uarr+=("$l_epu $l_eph")
         done <<< "$(awk -v pat="$l_valid_shells" -F: '$(NF) ~ pat { print $1 " " $(NF-1) }' /etc/passwd)"
         l_asize="${#a_uarr[@]}" # Here if we want to look at number of users before proceeding 
         [ "$l_asize " -gt "10000" ] && echo -e "\n ** INFO **\n - \"$l_asize\" Local interactive users found on the system\n - This may be a long running check\n"
         while read -r l_user l_home; do
         if [ -d "$l_home" ]; then
         l_mask='0027'
         l_max="$( printf '%o' $(( 0777 & ~$l_mask)) )"
         while read -r l_own l_mode; do
         [ "$l_user" != "$l_own" ] && l_hoout2="$l_hoout2\n - User: \"$l_user\" Home \"$l_home\" is owned by: \"$l_own\""
         if [ $(( $l_mode & $l_mask )) -gt 0 ]; then
         l_haout2="$l_haout2\n - User: \"$l_user\" Home \"$l_home\" is mode: \"$l_mode\" should be mode: \"$l_max\" or more restrictive"
         fi
         done <<< "$(stat -Lc '%U %#a' "$l_home")"
         else
         l_heout2="$l_heout2\n - User: \"$l_user\" Home \"$l_home\" Doesn't exist"
         fi
         done <<< "$(printf '%s\n' "${a_uarr[@]}")"
         [ -z "$l_heout2" ] && l_output="$l_output\n - home directories exist" || l_output2="$l_output2$l_heout2"
         [ -z "$l_hoout2" ] && l_output="$l_output\n - own their home directory" || l_output2="$l_output2$l_hoout2"
         [ -z "$l_haout2" ] && l_output="$l_output\n - home directories are mode: \"$l_max\" or more restrictive" || l_output2="$l_output2$l_haout2"
         [ -n "$l_output" ] && l_output=" - All local interactive users:$l_output"
         if [ -z "$l_output2" ]; then # If l_output2 is empty, we pass
         echo -e "\n- Audit Result:\n ** PASS **\n - * Correctly configured * :\n$l_output"
         else
         echo -e "\n- Audit Result:\n ** FAIL **\n - * Reasons for audit failure * :\n$l_output2"
         [ -n "$l_output" ] && echo -e "\n- * Correctly configured * :\n$l_output"
         fi
        }
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_6_2_11_redhat':
      command  => @(SABC_CMD/L),
        #!/usr/bin/env bash
        
        {
         l_output2=""
         l_valid_shells="^($( awk -F\/ '$NF != "nologin" {print}' /etc/shells | sed -rn '/^\//{s,/,\\\\/,g;p}' | paste -s -d '|' - ))$"
         unset a_uarr && a_uarr=() # Clear and initialize array
         while read -r l_epu l_eph; do # Populate array with users and user home location
         a_uarr+=("$l_epu $l_eph")
         done <<< "$(awk -v pat="$l_valid_shells" -F: '$(NF) ~ pat { print $1 " " $(NF-1) }' /etc/passwd)"
         l_asize="${#a_uarr[@]}" # Here if we want to look at number of users before proceeding 
         [ "$l_asize " -gt "10000" ] && echo -e "\n ** INFO **\n - \"$l_asize\" Local interactive users found on the system\n - This may be a long running process\n"
         while read -r l_user l_home; do
         if [ -d "$l_home" ]; then
         l_mask='0027'
         l_max="$( printf '%o' $(( 0777 & ~$l_mask)) )"
         while read -r l_own l_mode; do
         if [ "$l_user" != "$l_own" ]; then
         l_output2="$l_output2\n - User: \"$l_user\" Home \"$l_home\" is owned by: \"$l_own\"\n - changing ownership to: \"$l_user\"\n"
         chown "$l_user" "$l_home"
         fi
         if [ $(( $l_mode & $l_mask )) -gt 0 ]; then
         l_output2="$l_output2\n - User: \"$l_user\" Home \"$l_home\" is mode: \"$l_mode\" should be mode: \"$l_max\" or more restrictive\n - removing excess permissions\n"
         chmod g-w,o-rwx "$l_home"
         fi
         done <<< "$(stat -Lc '%U %#a' "$l_home")"
         else
         l_output2="$l_output2\n - User: \"$l_user\" Home \"$l_home\" Doesn't exist\n - Please create a home in accordance with local site policy"
         fi
         done <<< "$(printf '%s\n' "${a_uarr[@]}")"
         if [ -z "$l_output2" ]; then # If l_output2 is empty, we pass
         echo -e " - No modification needed to local interactive users home directories"
         else
         echo -e "\n$l_output2"
         fi
        }
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         l_output="" l_output2="" l_heout2="" l_hoout2="" l_haout2=""
         l_valid_shells="^($( awk -F\/ '$NF != "nologin" {print}' /etc/shells | sed -rn '/^\//{s,/,\\\\/,g;p}' | paste -s -d '|' - ))$"
         unset a_uarr && a_uarr=() # Clear and initialize array
         while read -r l_epu l_eph; do # Populate array with users and user home location
         a_uarr+=("$l_epu $l_eph")
         done <<< "$(awk -v pat="$l_valid_shells" -F: '$(NF) ~ pat { print $1 " " $(NF-1) }' /etc/passwd)"
         l_asize="${#a_uarr[@]}" # Here if we want to look at number of users before proceeding 
         [ "$l_asize " -gt "10000" ] && echo -e "\n ** INFO **\n - \"$l_asize\" Local interactive users found on the system\n - This may be a long running check\n"
         while read -r l_user l_home; do
         if [ -d "$l_home" ]; then
         l_mask='0027'
         l_max="$( printf '%o' $(( 0777 & ~$l_mask)) )"
         while read -r l_own l_mode; do
         [ "$l_user" != "$l_own" ] && l_hoout2="$l_hoout2\n - User: \"$l_user\" Home \"$l_home\" is owned by: \"$l_own\""
         if [ $(( $l_mode & $l_mask )) -gt 0 ]; then
         l_haout2="$l_haout2\n - User: \"$l_user\" Home \"$l_home\" is mode: \"$l_mode\" should be mode: \"$l_max\" or more restrictive"
         fi
         done <<< "$(stat -Lc '%U %#a' "$l_home")"
         else
         l_heout2="$l_heout2\n - User: \"$l_user\" Home \"$l_home\" Doesn't exist"
         fi
         done <<< "$(printf '%s\n' "${a_uarr[@]}")"
         [ -z "$l_heout2" ] && l_output="$l_output\n - home directories exist" || l_output2="$l_output2$l_heout2"
         [ -z "$l_hoout2" ] && l_output="$l_output\n - own their home directory" || l_output2="$l_output2$l_hoout2"
         [ -z "$l_haout2" ] && l_output="$l_output\n - home directories are mode: \"$l_max\" or more restrictive" || l_output2="$l_output2$l_haout2"
         [ -n "$l_output" ] && l_output=" - All local interactive users:$l_output"
         if [ -z "$l_output2" ]; then # If l_output2 is empty, we pass
         echo -e "\n- Audit Result:\n ** PASS **\n - * Correctly configured * :\n$l_output"
         else
         echo -e "\n- Audit Result:\n ** FAIL **\n - * Reasons for audit failure * :\n$l_output2"
         [ -n "$l_output" ] && echo -e "\n- * Correctly configured * :\n$l_output"
         fi
        }
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
