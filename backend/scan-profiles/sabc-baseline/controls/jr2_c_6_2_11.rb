control 'JR2.C.6.2.11' do
  title 'Ensure local interactive user home directories are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_11'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
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
umin=$(awk '/^\s*UID_MIN/{print $2}' /etc/login.defs); [ -n "$umin" ] || umin=1000
awk -F: -v m="$umin" '($3>=m && $7!~/(nologin|\/bin\/false)$/) {print $1":"$6}' /etc/passwd | \
while IFS=: read -r u h; do
  [ -d "$h" ] || exit 1
  set -- $(stat -Lc '%a %U %G' "$h")
mm=$1 o=$2 g=$3
  [ "$o" = "$u" ] || exit 1
  [ $(( 8#$mm & 8#0022 )) -eq 0 ] || exit 1
done
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
