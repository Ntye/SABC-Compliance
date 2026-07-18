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

/org/gnome/login-screen/disable-user-list
Example:
# printf '%s\n' "" "/org/gnome/login-screen/disable-user-list" >>
/etc/dconf/db/local.d/locks/60-login-screen
    4. Run the following script to comment out any incorrect settings in a local system-
       wide database keyfile:

#!/usr/bin/env bash

{
    l_parameter="disable-user-list=" l_value="false"
    while IFS= read -r -d $'\0' l_file; do
       grep -Psiq -- "^\h*$l_parameter$l_value(\b|\h*$)" "$l_file" && \
       sed -ri '/^\s*'"$l_parameter"'/s/^/# /g' "$l_file"
    done < <(find /etc/dconf/db -mindepth 2 -maxdepth 2 -type f -print0)
}

    5. Create or edit a local keyfile for machine-wide settings in '/etc/dconf/db/local.d/`
       with the following lines:

[org/gnome/login-screen]
disable-user-list=true
Example script:
#!/usr/bin/env bash

{
   l_file="/etc/dconf/db/local.d/60-login-screen"
   a_keyfile=("[org/gnome/login-screen]" "disable-user-list=true")
   if grep -Psq -- '^\h*\[org\/gnome\/login-screen\]' "$l_file"; then
      ! grep -Psiq -- '^\h*disable-user-list=true\b' "$l_file" && \
      sed -ri '/^\s*\[org\/gnome\/login-screen\]/a disable-user-list=true'
"$l_file"
      grep -Psiq -- '^\h*disable-user-list=false\b' "$l_file" && \
      sed -ri 's/^\s*(disable-user-list=)(false).*$/\1true/' "$l_file"
   else
      printf '%s\n' "" "${a_keyfile[@]}" >> "$l_file"
   fi
}

    6. Run the following command to update the dconf databases:

# dconf update
Note: Users must log out and back in again before the system-wide settings take effect.
