#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true

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
