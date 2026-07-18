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

/org/gnome/login-screen/banner-message-enable
/org/gnome/login-screen/banner-message-text
Example:
# printf '%s\n' "" "/org/gnome/login-screen/banner-message-enable" \
"/org/gnome/login-screen/banner-message-text" >>
/etc/dconf/db/local.d/locks/60-banner-message

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
    l_parameter="banner-message-enable=" l_value="false"; f_key_file_fix
    l_parameter="banner-message-text=" l_value="(['\"]{2})?"; f_key_file_fix
}

    5. Create or edit a local keyfile for machine-wide settings in '/etc/dconf/db/local.d/`
       with the following lines to set the login banner configuration:

[org/gnome/login-screen]
banner-message-enable=true
banner-message-text='Type the banner message here.'
Example script:
#!/usr/bin/env bash

{
   l_file="/etc/dconf/db/local.d/60-banner-message"
   l_banner="'Authorized uses only. All activity may be monitored and
reported'"
   a_keyfile=("[org/gnome/login-screen]" "banner-message-enable=true" \
   "banner-message-text=$l_banner")
   if grep -Psq -- '^\h*\[org\/gnome\/login-screen\]' "$l_file"; then
      ! grep -Psiq -- '^\h*banner-message-enable=true\b' "$l_file" && \
      sed -ri '/^\s*\[org\/gnome\/login-screen\]/a banner-message-
enable=true' "$l_file"
      ! grep -Psiq -- '^\h*banner-message-text=[^#\n\r]+' "$l_file" && \
      sed -ri '/^\s*\[org\/gnome\/login-screen\]/a banner-message-
text='"$l_banner"'' "$l_file"
   else
      printf '%s\n' "" "${a_keyfile[@]}" >> "$l_file"
   fi
}

    6. Run the following command to update the dconf database:

# dconf update
Note:

   •    banner-message-text should be set in accordance with local site policy
   •    Users must log out and back in again before the system-wide settings take effect.
   •    There is no character limit for the banner message. gnome-shell autodetects
        longer stretches of text and enters two column mode.
   •    The banner message cannot be read from an external file
