# JR2.C.1.7.6 (CIS Level 1) — Ensure GDM disabling automatic mounting of removable media is not overridden.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_7_6 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_7_6_debian':
      command  => @(SABC_CMD/L),
        #!/usr/bin/env bash
        
        {
         # Check if GNMOE Desktop Manager is installed. If package isn't installed, recommendation is Not Applicable\n
         # determine system's package manager
         l_pkgoutput=""
         if command -v dpkg-query > /dev/null 2> then
         l_pq="dpkg-query -W"
         elif command -v rpm > /dev/null 2> then
         l_pq="rpm -q"
         fi
         # Check if GDM is installed
         l_pcl="gdm gdm3" # Space separated list of packages to check
         for l_pn in $l_pcl; do
         $l_pq "$l_pn" > /dev/null 2>&1 && l_pkgoutput="y" && echo -e "\n - Package: \"$l_pn\" exists on the system\n - remediating configuration if needed"
         done
         # Check configuration (If applicable)
         if [ -n "$l_pkgoutput" ]; then
         # Look for automount to determine profile in use, needed for remaining tests
         l_kfd="/etc/dconf/db/$(grep -Psril '^\h*automount\b' /etc/dconf/db/*/ | awk -F'/' '{split($(NF-1),a,".");print a[1]}').d" #set directory of key file to be locked
         # Look for automount-open to determine profile in use, needed for remaining tests
         l_kfd2="/etc/dconf/db/$(grep -Psril '^\h*automount-open\b' /etc/dconf/db/*/ | awk -F'/' '{split($(NF-1),a,".");print a[1]}').d" #set directory of key file to be locked
         if [ -d "$l_kfd" ]; then # If key file directory doesn't exist, options can't be locked
         if grep -Priq '^\h*\/org/gnome\/desktop\/media-handling\/automount\b' "$l_kfd"; then
         echo " - \"automount\" is locked in \"$(grep -Pril '^\h*\/org/gnome\/desktop\/media-handling\/automount\b' "$l_kfd")\""
         else
         echo " - creating entry to lock \"automount\""
         [ ! -d "$l_kfd"/locks ] && echo "creating directory $l_kfd/locks" && mkdir "$l_kfd"/locks
         {
         echo -e '\n# Lock desktop media-handling automount setting'
         echo '/org/gnome/desktop/media-handling/automount'
         } >> "$l_kfd"/locks/00-media-automount 
         fi
         else
         echo -e " - \"automount\" is not set so it can not be locked\n - Please follow Recommendation \"Ensure GDM automatic mounting of removable media is disabled\" and follow this Recommendation again"
         fi
         if [ -d "$l_kfd2" ]; then # If key file directory doesn't exist, options can't be locked
         if grep -Priq '^\h*\/org/gnome\/desktop\/media-handling\/automount-open\b' "$l_kfd2"; then
         echo " - \"automount-open\" is locked in \"$(grep -Pril '^\h*\/org/gnome\/desktop\/media-handling\/automount-open\b' "$l_kfd2")\""
         else
         echo " - creating entry to lock \"automount-open\""
         [ ! -d "$l_kfd2"/locks ] && echo "creating directory $l_kfd2/locks" && mkdir "$l_kfd2"/locks
         {
         echo -e '\n# Lock desktop media-handling automount-open setting'
         echo '/org/gnome/desktop/media-handling/automount-open'
         } >> "$l_kfd2"/locks/00-media-automount
         fi
         else
         echo -e " - \"automount-open\" is not set so it can not be locked\n - Please follow Recommendation \"Ensure GDM automatic mounting of removable media is disabled\" and follow this Recommendation again"
         fi
         # update dconf database
         dconf update
         else
         echo -e " - GNOME Desktop Manager package is not installed on the system\n - Recommendation is not applicable"
         fi
        }
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         # Check if GNOME Desktop Manager is installed. If package isn't installed, recommendation is Not Applicable\n
         # determine system's package manager
         l_pkgoutput=""
         if command -v dpkg-query > /dev/null 2> then
         l_pq="dpkg-query -W"
         elif command -v rpm > /dev/null 2> then
         l_pq="rpm -q"
         fi
         # Check if GDM is installed
         l_pcl="gdm gdm3" # Space separated list of packages to check
         for l_pn in $l_pcl; do
         $l_pq "$l_pn" > /dev/null 2>&1 && l_pkgoutput="$l_pkgoutput\n - Package: \"$l_pn\" exists on the system\n - checking configuration"
         done
         # Check configuration (If applicable)
         if [ -n "$l_pkgoutput" ]; then
         l_output="" l_output2=""
         # Look for idle-delay to determine profile in use, needed for remaining tests
         l_kfd="/etc/dconf/db/$(grep -Psril '^\h*automount\b' /etc/dconf/db/*/ | awk -F'/' '{split($(NF-1),a,".");print a[1]}').d" #set directory of key file to be locked
         l_kfd2="/etc/dconf/db/$(grep -Psril '^\h*automount-open\b' /etc/dconf/db/*/ | awk -F'/' '{split($(NF-1),a,".");print a[1]}').d" #set directory of key file to be locked
         if [ -d "$l_kfd" ]; then # If key file directory doesn't exist, options can't be locked
         if grep -Piq '^\h*\/org/gnome\/desktop\/media-handling\/automount\b' "$l_kfd"; then
         l_output="$l_output\n - \"automount\" is locked in \"$(grep -Pil '^\h*\/org/gnome\/desktop\/media-handling\/automount\b' "$l_kfd")\""
         else
         l_output2="$l_output2\n - \"automount\" is not locked"
         fi
         else
         l_output2="$l_output2\n - \"automount\" is not set so it can not be locked"
         fi
         if [ -d "$l_kfd2" ]; then # If key file directory doesn't exist, options can't be locked
         if grep -Piq '^\h*\/org/gnome\/desktop\/media-handling\/automount-open\b' "$l_kfd2"; then
         l_output="$l_output\n - \"lautomount-open\" is locked in \"$(grep -Pril '^\h*\/org/gnome\/desktop\/media-handling\/automount-open\b' "$l_kfd2")\""
         else
         l_output2="$l_output2\n - \"automount-open\" is not locked"
         fi
         else
         l_output2="$l_output2\n - \"automount-open\" is not set so it can not be locked"
         fi
         else
         l_output="$l_output\n - GNOME Desktop Manager package is not installed on the system\n - Recommendation is not applicable"
         fi
         # Report results. If no failures output in l_output2, we pass
         [ -n "$l_pkgoutput" ] && echo -e "\n$l_pkgoutput"
         if [ -z "$l_output2" ]; then
         echo -e "\n- Audit Result:\n ** PASS **\n$l_output\n"
         else
         echo -e "\n- Audit Result:\n ** FAIL **\n - Reason(s) for audit failure:\n$l_output2\n"
         [ -n "$l_output" ] && echo -e "\n- Correctly set:\n$l_output\n"
         fi
        }
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_7_6_redhat':
      command  => @(SABC_CMD/L),
        #!/usr/bin/env bash
        
        {
         # Check if GNMOE Desktop Manager is installed. If package isn't installed, recommendation is Not Applicable\n
         # determine system's package manager
         l_pkgoutput=""
         if command -v dpkg-query > /dev/null 2> then
         l_pq="dpkg-query -W"
         elif command -v rpm > /dev/null 2> then
         l_pq="rpm -q"
         fi
         # Check if GDM is installed
         l_pcl="gdm gdm3" # Space separated list of packages to check
         for l_pn in $l_pcl; do
         $l_pq "$l_pn" > /dev/null 2>&1 && l_pkgoutput="y" && echo -e "\n - Package: \"$l_pn\" exists on the system\n - remediating configuration if needed"
         done
         # Check configuration (If applicable)
         if [ -n "$l_pkgoutput" ]; then
         # Look for automount to determine profile in use, needed for remaining tests
         l_kfd="/etc/dconf/db/$(grep -Psril '^\h*automount\b' /etc/dconf/db/*/ | awk -F'/' '{split($(NF-1),a,".");print a[1]}').d" #set directory of key file to be locked
         # Look for automount-open to determine profile in use, needed for remaining tests
         l_kfd2="/etc/dconf/db/$(grep -Psril '^\h*automount-open\b' /etc/dconf/db/*/ | awk -F'/' '{split($(NF-1),a,".");print a[1]}').d" #set directory of key file to be locked
         if [ -d "$l_kfd" ]; then # If key file directory doesn't exist, options can't be locked
         if grep -Priq '^\h*\/org/gnome\/desktop\/media-handling\/automount\b' "$l_kfd"; then
         echo " - \"automount\" is locked in \"$(grep -Pril '^\h*\/org/gnome\/desktop\/media-handling\/automount\b' "$l_kfd")\""
         else
         echo " - creating entry to lock \"automount\""
         [ ! -d "$l_kfd"/locks ] && echo "creating directory $l_kfd/locks" && mkdir "$l_kfd"/locks
         {
         echo -e '\n# Lock desktop media-handling automount setting'
         echo '/org/gnome/desktop/media-handling/automount'
         } >> "$l_kfd"/locks/00-media-automount 
         fi
         else
         echo -e " - \"automount\" is not set so it can not be locked\n - Please follow Recommendation \"Ensure GDM automatic mounting of removable media is disabled\" and follow this Recommendation again"
         fi
         if [ -d "$l_kfd2" ]; then # If key file directory doesn't exist, options can't be locked
         if grep -Priq '^\h*\/org/gnome\/desktop\/media-handling\/automount-open\b' "$l_kfd2"; then
         echo " - \"automount-open\" is locked in \"$(grep -Pril '^\h*\/org/gnome\/desktop\/media-handling\/automount-open\b' "$l_kfd2")\""
         else
         echo " - creating entry to lock \"automount-open\""
         [ ! -d "$l_kfd2"/locks ] && echo "creating directory $l_kfd2/locks" && mkdir "$l_kfd2"/locks
         {
         echo -e '\n# Lock desktop media-handling automount-open setting'
         echo '/org/gnome/desktop/media-handling/automount-open'
         } >> "$l_kfd2"/locks/00-media-automount
         fi
         else
         echo -e " - \"automount-open\" is not set so it can not be locked\n - Please follow Recommendation \"Ensure GDM automatic mounting of removable media is disabled\" and follow this Recommendation again"
         fi
         # update dconf database
         dconf update
         else
         echo -e " - GNOME Desktop Manager package is not installed on the system\n - Recommendation is not applicable"
         fi
        }
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         # Check if GNOME Desktop Manager is installed. If package isn't installed, recommendation is Not Applicable\n
         # determine system's package manager
         l_pkgoutput=""
         if command -v dpkg-query > /dev/null 2> then
         l_pq="dpkg-query -W"
         elif command -v rpm > /dev/null 2> then
         l_pq="rpm -q"
         fi
         # Check if GDM is installed
         l_pcl="gdm gdm3" # Space separated list of packages to check
         for l_pn in $l_pcl; do
         $l_pq "$l_pn" > /dev/null 2>&1 && l_pkgoutput="$l_pkgoutput\n - Package: \"$l_pn\" exists on the system\n - checking configuration"
         done
         # Check configuration (If applicable)
         if [ -n "$l_pkgoutput" ]; then
         l_output="" l_output2=""
         # Look for idle-delay to determine profile in use, needed for remaining tests
         l_kfd="/etc/dconf/db/$(grep -Psril '^\h*automount\b' /etc/dconf/db/*/ | awk -F'/' '{split($(NF-1),a,".");print a[1]}').d" #set directory of key file to be locked
         l_kfd2="/etc/dconf/db/$(grep -Psril '^\h*automount-open\b' /etc/dconf/db/*/ | awk -F'/' '{split($(NF-1),a,".");print a[1]}').d" #set directory of key file to be locked
         if [ -d "$l_kfd" ]; then # If key file directory doesn't exist, options can't be locked
         if grep -Piq '^\h*\/org/gnome\/desktop\/media-handling\/automount\b' "$l_kfd"; then
         l_output="$l_output\n - \"automount\" is locked in \"$(grep -Pil '^\h*\/org/gnome\/desktop\/media-handling\/automount\b' "$l_kfd")\""
         else
         l_output2="$l_output2\n - \"automount\" is not locked"
         fi
         else
         l_output2="$l_output2\n - \"automount\" is not set so it can not be locked"
         fi
         if [ -d "$l_kfd2" ]; then # If key file directory doesn't exist, options can't be locked
         if grep -Piq '^\h*\/org/gnome\/desktop\/media-handling\/automount-open\b' "$l_kfd2"; then
         l_output="$l_output\n - \"lautomount-open\" is locked in \"$(grep -Pril '^\h*\/org/gnome\/desktop\/media-handling\/automount-open\b' "$l_kfd2")\""
         else
         l_output2="$l_output2\n - \"automount-open\" is not locked"
         fi
         else
         l_output2="$l_output2\n - \"automount-open\" is not set so it can not be locked"
         fi
         else
         l_output="$l_output\n - GNOME Desktop Manager package is not installed on the system\n - Recommendation is not applicable"
         fi
         # Report results. If no failures output in l_output2, we pass
         [ -n "$l_pkgoutput" ] && echo -e "\n$l_pkgoutput"
         if [ -z "$l_output2" ]; then
         echo -e "\n- Audit Result:\n ** PASS **\n$l_output\n"
         else
         echo -e "\n- Audit Result:\n ** FAIL **\n - Reason(s) for audit failure:\n$l_output2\n"
         [ -n "$l_output" ] && echo -e "\n- Correctly set:\n$l_output\n"
         fi
        }
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
