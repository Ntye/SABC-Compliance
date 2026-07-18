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
       lines to lock the login banner configuration:

/org/gnome/desktop/session/idle-delay
/org/gnome/desktop/screensaver/lock-delay
Example:
# printf '%s\n' "" "/org/gnome/desktop/session/idle-delay" \
"/org/gnome/desktop/screensaver/lock-delay" >>
/etc/dconf/db/local.d/locks/60-screensaver
    4. Run the following script to comment out any incorrect settings in a local system-
       wide database keyfile:

#!/usr/bin/env bash

{
   f_key_file_fix()
   {
      while IFS= read -r -d $'\0' l_file; do
         grep -Psiq -- "^\h*$l_parameter\h+$l_value(\b|\h*$)" "$l_file" && \
         sed -ri '/^\s*'"$l_parameter"'/s/^/# /g' "$l_file"
      done < <(find /etc/dconf/db -mindepth 2 -maxdepth 2 -type f -print0)
   }
   l_parameter="idle-delay=uint32" l_value="(0|90[1-9]|9[1-9][0-9]|1[0-
9]{3,})"; f_key_file_fix
   l_parameter="lock-delay=uint32" l_value="([6-9]|[1-9][0-9]+)";
f_key_file_fix
}

    5. Create or edit a local keyfile for machine-wide settings in '/etc/dconf/db/local.d/`
       with the following lines:

[org/gnome/desktop/session]
idle-delay=uint32 900

[org/gnome/desktop/screensaver]
lock-delay=uint32 5

    •   idle-delay=uint32 {n} - Number of seconds of inactivity before the screen goes
        blank. Should be '900' (15 minutes) or less, and not 0 (disabled)
    •   lock-delay=uint32 {n} - Number of seconds after the screen is blank before
        locking the screen. Should be 5 or less
Example script:
#!/usr/bin/env bash

{
   l_file="/etc/dconf/db/local.d/60-screensaver"
   a_keyfile1=("[org/gnome/desktop/session]" "idle-delay=uint32 900")
   a_keyfile2=("[org/gnome/desktop/screensaver]" "lock-delay=uint32 5")
   if grep -Psq -- '^\h*\[org\/gnome\/desktop\/session\]' "$l_file"; then
      ! grep -Psiq -- '^\h*idle-delay=' "$l_file" && \
      sed -ri '/^\s*\[org\/gnome\/desktop\/session\]/a idle-delay=uint32 900'
"$l_file"
      grep -Psiq -- '^\h*idle-delay=uint32\h+(0|90[1-9]|9[1-9][0-9]|[1-9][0-
9]{3,})\b' \
      "$l_file" && sed -ri 's/^\s*(idle-delay=uint32)\s+([0-9]|[1-9][0-
9]+).*$/\1 900/' "$l_file"
   else
      printf '%s\n' "" "${a_keyfile1[@]}" >> "$l_file"
   fi
   if grep -Psq -- '^\h*\[org\/gnome\/desktop\/screensaver\]' "$l_file"; then
      ! grep -Psiq -- '^\h*lock-delay=' "$l_file" && \
      sed -ri '/^\s*\[org\/gnome\/desktop\/screensaver\]/a lock-delay=uint32
5' "$l_file"
      grep -Psiq -- '^\h*lock-delay=uint32\h+([6-9]|[1-9][0-9]+)\b' "$l_file"
&& \
      sed -ri 's/^\s*(lock-delay=uint32)\s+([6-9]|[1-9][0-9]+).*$/\1 5/'
"$l_file"
   else
      printf '%s\n' "" "${a_keyfile2[@]}" >> "$l_file"
   fi
}

    6. Run the following command to update the dconf database:

# dconf update
Note: Users must log out and back in again before the system-wide settings take effect.
