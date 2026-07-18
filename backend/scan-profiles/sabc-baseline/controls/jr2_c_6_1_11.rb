control 'JR2.C.6.1.11' do
  title 'Ensure world writable files and directories are secured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_1_11'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/usr/bin/env bash
      
      {
       l_output="" l_output2=""
       l_smask='01000'
       a_path=(); a_arr=(); a_file=(); a_dir=() # Initialize arrays
       a_path=(! -path "/run/user/*" -a ! -path "/proc/*" -a ! -path "*/containerd/*" -a ! -path "*/kubelet/pods/*" -a ! -path "/sys/kernel/security/apparmor/*" -a ! -path "/snap/*" -a ! -path "/sys/fs/cgroup/memory/*")
       while read -r l_bfs; do
       a_path+=( -a ! -path ""$l_bfs"/*")
       done < <(findmnt -Dkerno fstype,target | awk '$1 ~ /^\s*(nfs|proc|smb)/ {print $2}')
       # Populate array with files that will possibly fail one of the audits
       while IFS= read -r -d $'\0' l_file; do
       [ -e "$l_file" ] && a_arr+=("$(stat -Lc '%n^%#a' "$l_file")")
       done < <(find / \( "${a_path[@]}" \) \( -type f -o -type d \) -perm -0002 -print0 2>/dev/null)
       while IFS="^" read -r l_fname l_mode; do # Test files in the array
       [ -f "$l_fname" ] && a_file+=("$l_fname") # Add WR files
       if [ -d "$l_fname" ]; then # Add directories w/o sticky bit
       [ ! $(( $l_mode & $l_smask )) -gt 0 ] && a_dir+=("$l_fname")
       fi
       done < <(printf '%s\n' "${a_arr[@]}")
       if ! (( ${#a_file[@]} > 0 )); then
       l_output="$l_output\n - No world writable files exist on the local filesystem."
       else
       l_output2="$l_output2\n - There are \"$(printf '%s' "${#a_file[@]}")\" World writable files on the system.\n - The following is a list of World writable files:\n$(printf '%s\n' "${a_file[@]}")\n - end of list\n"
       fi
       if ! (( ${#a_dir[@]} > 0 )); then
       l_output="$l_output\n - Sticky bit is set on world writable directories on the local filesystem."
       else
       l_output2="$l_output2\n - There are \"$(printf '%s' "${#a_dir[@]}")\" World writable directories without the sticky bit on the system.\n - The following is a list of World writable directories without the sticky bit:\n$(printf '%s\n' "${a_dir[@]}")\n - end of list\n"
       fi
       unset a_path; unset a_arr; unset a_file; unset a_dir # Remove arrays
       # If l_output2 is empty, we pass
       if [ -z "$l_output2" ]; then
       echo -e "\n- Audit Result:\n ** PASS **\n - * Correctly configured * :\n$l_output\n"
       else
       echo -e "\n- Audit Result:\n ** FAIL **\n - * Reasons for audit failure * :\n$l_output2"
       [ -n "$l_output" ] && echo -e "- * Correctly configured * :\n$l_output\n"
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
      
      {
         a_output=() a_output2=() a_file=() a_dir=()
         l_smask='01000' l_limit="50"
         a_path=(-path "*/containers/storage/*" -o -path "*/containerd/*" -o -path
      "*/kubelet/*" -o -path "/sys/*" -o -path "/snap/*" -o -path "/boot/efi/*")
         while IFS= read -r l_mount; do
            while IFS= read -r -d $'\0' l_file; do
               if [ -e "$l_file" ]; then
                   [ -f "$l_file" ] && a_file+=("$l_file")
                   if [ -d "$l_file" ]; then
                      l_mode="$(stat -Lc '%#a' "$l_file")"
                      [ ! $(( $l_mode & $l_smask )) -gt 0 ] && a_dir+=("$l_file")
                   fi
               fi
            done < <(find "$l_mount" -mount -xdev \( "${a_path[@]}" \) -prune -o \( -type f
      -o -type d \) -perm -0002 -print0 2> /dev/null)
         done < <(findmnt -Dkerno fstype,target | awk '($1 !~
      /^\s*(nfs|proc|cifs|smb|vfat|iso9660|efivarfs|selinuxfs|ncpfs)/ && $2 !~
      /^(\/run|\/tmp|\/var\/tmp)(\/|$)/){print $2}')
         if [ "${#a_file[@]}" -le 0 ]; then
            a_output+=(" - No world writable files exist on the local filesystem.")
         else
            a_output2+=("" " - There are \"${#a_file[@]}\" World writable files on the
      system." \
            "    - The following is a list of World writable files:" \
            "${a_file[@]:0:$l_limit}" "    - end of list")
         fi
         if [ "${#a_dir[@]}" -le 0 ]; then
            a_output+=(" - Sticky bit is set on world writable directories on the local
      filesystem.")
         else
            a_output2+=("" " - There are \"${#a_dir[@]}\" World writable directories without
      the sticky bit on the system." \
            "    - The following is a list of World writable directories without the sticky
      bit:" \
            "${a_dir[@]:0:$l_limit}" "    - end of list")
         fi
         if [ "${#a_output2[@]}" -le 0 ]; then
            printf '%s\n' "" "- Audit Result:" " ** PASS **" "${a_output[@]}"
         else
            printf '%s\n' "" "- Audit Result:" " ** FAIL **" " * Reasons for audit failure
      *" "${a_output2[@]}" ""
            [ "${#a_output[@]}" -gt 0 ] && printf '%s\n' "- Correctly set:" "${a_output[@]}"
         fi
      }
      
      Note: On systems with a large number of files and/or directories, this audit may be a
      long running process
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
