control 'JR2.C.4.2.1' do
  title 'Ensure permissions on /etc/ssh/sshd_config are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_2_1'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
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
exec /bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
f=/etc/ssh/sshd_config
[ -e "$f" ] || exit 1
set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
[ "$o" = "root" ] || exit 1
{ [ "$g" = "root" ]; } || exit 1
[ $(( 8#$m & ~8#600 & 8#7777 )) -eq 0 ] || exit 1
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
