#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true

{
    l_dir="/etc/dconf/profile/"
    [ ! -d "$l_dir" ] && mkdir /etc/dconf/profile/
    ! grep -Psq '^\h*user-db:user\b' "$l_dir/user" && \
    printf '%s\n' "" "user-db:user" >> "$l_dir/user"
    ! grep -Psq '^\h*system-db:local\b' "$l_dir/user" && \
    sed -ri '/^\s*user-db:user/a system-db:local' "$l_dir/user"
}

    2. Run the following command to create the /etc/dconf/db/local.d/ and
       /etc/dconf/db/local.d/locks/ directories if either does not exist:

# [ ! -d "/etc/dconf/db/local.d/locks/" ] && mkdir -p
/etc/dconf/db/local.d/locks/

    3. Create or edit a file in /etc/dconf/db/local.d/locks/ and add the following
       lines:

/org/gnome/desktop/media-handling/automount
/org/gnome/desktop/media-handling/automount-open
Example:
# printf '%s\n' "" "/org/gnome/desktop/media-handling/automount" \
"/org/gnome/desktop/media-handling/automount-open" >> \
/etc/dconf/db/local.d/locks/60-media-automount
    4. Run the following script to comment out any incorrect settings in a local system-
       wide database keyfile:

#!/usr/bin/env bash

{
    f_key_file_fix()
    {
       while IFS= read -r -d $'\0' l_file; do
          grep -Psiq -- "^\h*$l_parameter$l_value(\b|\h*$)" "$l_file" && \
          sed -ri '/^\s*'"$l_parameter"'/s/^/# /g' "$l_file"
       done < <(find /etc/dconf/db -mindepth 2 -maxdepth 2 -type f -print0)
    }
    l_parameter="automount=" l_value="true"; f_key_file_fix
    l_parameter="automount-open=" l_value="true"; f_key_file_fix
}

    5. Create or edit a local keyfile for machine-wide settings in '/etc/dconf/db/local.d/`
       with the following lines:

[org/gnome/desktop/media-handling]
automount=false
automount-open=false
Example script:
#!/usr/bin/env bash

{
   l_file="/etc/dconf/db/local.d/60-media-automount"
   a_keyfile=("[org/gnome/desktop/media-handling]" "automount=false"
"automount-open=false")
   if grep -Psq -- '^\h*\[org\/gnome\/desktop\/media-handling\]' "$l_file";
then
      ! grep -Psiq -- '^\h*automount-open=false\b' "$l_file" && \
      sed -ri '/^\s*\[org\/gnome\/desktop\/media-handling\]/a automount-
open=false' "$l_file"
      ! grep -Psiq -- '^\h*automount=false\b' "$l_file" && \
      sed -ri '/^\s*\[org\/gnome\/desktop\/media-handling\]/a
automount=false' "$l_file"
      grep -Psiq -- '^\h*automount=true\b' "$l_file" && \
      sed -ri 's/^\s*(automount=)(true).*$/\1fales/' "$l_file"
      grep -Psiq -- '^\h*automount-open=true\b' "$l_file" && \
      sed -ri 's/^\s*(automount-open=)(true).*$/\1fales/' "$l_file"
   else
      printf '%s\n' "" "${a_keyfile[@]}" >> "$l_file"
   fi
}

    6. Run the following command to update the dconf databases:

# dconf update
Note: Users must log out and back in again before the system-wide settings take effect.
