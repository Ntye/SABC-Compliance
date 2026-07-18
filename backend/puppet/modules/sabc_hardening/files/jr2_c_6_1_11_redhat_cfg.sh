#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true

{
   l_smask='01000' a_file=() a_dir=()
   a_path=(-path "*/containers/storage/*" -o -path "*/containerd/*" -o -path
"*/kubelet/*" -o -path "/sys/*" -o -path "/snap/*" -o -path "/boot/efi/*")
   while IFS= read -r l_mount; do
      while IFS= read -r -d $'\0' l_file; do
         if [ -e "$l_file" ]; then
            l_mode="$(stat -Lc '%#a' "$l_file")"
            if [ -f "$l_file" ]; then # Remove excess permissions from WW
files
               echo -e " - File: \"$l_file\" is mode: \"$l_mode\"\n -
removing write permission on \"$l_file\" from \"other\""
               chmod o-w "$l_file"
            fi
            if [ -d "$l_file" ]; then # Add sticky bit
               if [ ! $(( $l_mode & $l_smask )) -gt 0 ]; then
                  echo -e " - Directory: \"$l_file\" is mode: \"$l_mode\" and
doesn't have the sticky bit set\n - Adding the sticky bit"
                  chmod a+t "$l_file"
               fi
            fi
         fi
      done < <(find "$l_mount" -mount -xdev \( "${a_path[@]}" \) \( -type f -
o -type d \) -perm -0002 -print0 2> /dev/null)
   done < <(findmnt -Dkerno fstype,target | awk '($1 !~
/^\s*(nfs|proc|cifs|smb|vfat|iso9660|efivarfs|selinuxfs|ncpfs)/ && $2 !~
/^(\/run|\/tmp|\/var\/tmp)(\/|$)/){print $2}')
}
