control 'JR2.C.6.1.12' do
  title 'Ensure no unowned or ungrouped files or directories exist.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_1_12'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
#!/usr/bin/env bash

{
 l_output="" l_output2=""
 a_path=(); a_arr=(); a_nouser=(); a_nogroup=() # Initialize arrays
 a_path=(! -path "/run/user/*" -a ! -path "/proc/*" -a ! -path "*/containerd/*" -a ! -path "*/kubelet/pods/*")
 while read -r l_bfs; do
 a_path+=( -a ! -path ""$l_bfs"/*")
 done < <(findmnt -Dkerno fstype,target | awk '$1 ~ /^\s*(nfs|proc|smb)/ {print $2}')
 while IFS= read -r -d $'\0' l_file; do
 [ -e "$l_file" ] && a_arr+=("$(stat -Lc '%n^%U^%G' "$l_file")") && echo "Adding: $l_file"
 done < <(find / \( "${a_path[@]}" \) \( -type f -o -type d \) \( -nouser -o -nogroup \) -print0 2> /dev/null)
 while IFS="^" read -r l_fname l_user l_group; do # Test files in the array
 [ "$l_user" = "UNKNOWN" ] && a_nouser+=("$l_fname")
 [ "$l_group" = "UNKNOWN" ] && a_nogroup+=("$l_fname")
 done <<< "$(printf '%s\n' "${a_arr[@]}")"
 if ! (( ${#a_nouser[@]} > 0 )); then
 l_output="$l_output\n - No unowned files or directories exist on the local filesystem."
 else
 l_output2="$l_output2\n - There are \"$(printf '%s' "${#a_nouser[@]}")\" unowned files or directories on the system.\n - The following is a list of unowned files and/or directories:\n$(printf '%s\n' "${a_nouser[@]}")\n - end of list"
 fi
 if ! (( ${#a_nogroup[@]} > 0 )); then
 l_output="$l_output\n - No ungrouped files or directories exist on the local filesystem."
 else
 l_output2="$l_output2\n - There are \"$(printf '%s' "${#a_nogroup[@]}")\" ungrouped files or directories on the system.\n - The following is a list of ungrouped files and/or directories:\n$(printf '%s\n' "${a_nogroup[@]}")\n - end of list"
 fi 
 unset a_path; unset a_arr ; unset a_nouser; unset a_nogroup # Remove arrays
 if [ -z "$l_output2" ]; then # If l_output2 is empty, we pass
 echo -e "\n- Audit Result:\n ** PASS **\n - * Correctly configured * :\n$l_output\n"
 else
 echo -e "\n- Audit Result:\n ** FAIL **\n - * Reasons for audit failure * :\n$l_output2"
 [ -n "$l_output" ] && echo -e "\n- * Correctly configured * :\n$l_output\n"
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
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
#!/usr/bin/env bash
find / -xdev \( -path /proc -o -path /sys -o -path /run \) -prune \
  -o \( -nouser -o -nogroup \) -print 2>/dev/null | grep -q . && exit 1
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
