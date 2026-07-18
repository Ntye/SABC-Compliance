control 'JR2.C.1.7.5' do
  title 'Ensure GDM automatic mounting of removable media is disabled.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_7_5'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/usr/bin/env bash
      
      {
       l_pkgoutput="" l_output="" l_output2=""
       # Check if GNOME Desktop Manager is installed. If package isn't installed, recommendation is Not Applicable\n
       # determine system's package manager
       if command -v dpkg-query > /dev/null 2>&1; then
       l_pq="dpkg-query -W"
       elif command -v rpm > /dev/null 2>&1; then
       l_pq="rpm -q"
       fi
       # Check if GDM is installed
       l_pcl="gdm gdm3" # Space separated list of packages to check
       for l_pn in $l_pcl; do
       $l_pq "$l_pn" > /dev/null 2>&1 && l_pkgoutput="$l_pkgoutput\n - Package: \"$l_pn\" exists on the system\n - checking configuration"
       done
       # Check configuration (If applicable)
       if [ -n "$l_pkgoutput" ]; then
       echo -e "$l_pkgoutput"
       # Look for existing settings and set variables if they exist
       l_kfile="$(grep -Prils -- '^\h*automount\b' /etc/dconf/db/*.d)"
       l_kfile2="$(grep -Prils -- '^\h*automount-open\b' /etc/dconf/db/*.d)"
       # Set profile name based on dconf db directory ({PROFILE_NAME}.d)
       if [ -f "$l_kfile" ]; then
       l_gpname="$(awk -F\/ '{split($(NF-1),a,".");print a[1]}' <<< "$l_kfile")"
       elif [ -f "$l_kfile2" ]; then
       l_gpname="$(awk -F\/ '{split($(NF-1),a,".");print a[1]}' <<< "$l_kfile2")"
       fi
       # If the profile name exist, continue checks
       if [ -n "$l_gpname" ]; then
       l_gpdir="/etc/dconf/db/$l_gpname.d"
       # Check if profile file exists
       if grep -Pq -- "^\h*system-db:$l_gpname\b" /etc/dconf/profile/*; then
       l_output="$l_output\n - dconf database profile file \"$(grep -Pl -- "^\h*system-db:$l_gpname\b" /etc/dconf/profile/*)\" exists"
       else
       l_output2="$l_output2\n - dconf database profile isn't set"
       fi
       # Check if the dconf database file exists
       if [ -f "/etc/dconf/db/$l_gpname" ]; then
       l_output="$l_output\n - The dconf database \"$l_gpname\" exists"
       else
       l_output2="$l_output2\n - The dconf database \"$l_gpname\" doesn't exist"
       fi
       # check if the dconf database directory exists
       if [ -d "$l_gpdir" ]; then
       l_output="$l_output\n - The dconf directory \"$l_gpdir\" exitst"
       else
       l_output2="$l_output2\n - The dconf directory \"$l_gpdir\" doesn't exist"
       fi
       # check automount setting
       if grep -Pqrs -- '^\h*automount\h*=\h*false\b' "$l_kfile"; then
       l_output="$l_output\n - \"automount\" is set to false in: \"$l_kfile\""
       else
       l_output2="$l_output2\n - \"automount\" is not set correctly"
       fi
       # check automount-open setting
       if grep -Pqs -- '^\h*automount-open\h*=\h*false\b' "$l_kfile2"; then
       l_output="$l_output\n - \"automount-open\" is set to false in: \"$l_kfile2\""
       else
       l_output2="$l_output2\n - \"automount-open\" is not set correctly"
       fi
       else
       # Setings don't exist. Nothing further to check
       l_output2="$l_output2\n - neither \"automount\" or \"automount-open\" is set"
       fi
       else
       l_output="$l_output\n - GNOME Desktop Manager package is not installed on the system\n - Recommendation is not applicable"
       fi
       # Report results. If no failures output in l_output2, we pass
       if [ -z "$l_output2" ]; then
       echo -e "\n- Audit Result:\n ** PASS **\n$l_output\n"
       else
       echo -e "\n- Audit Result:\n ** FAIL **\n - Reason(s) for audit failure:\n$l_output2\n"
       [ -n "$l_output" ] && echo -e "\n- Correctly set:\n$l_output\n"
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
      #!/bin/bash
      rpm -q gdm >/dev/null 2>&1 || exit 101
      grep -Eqrs 'automount=false' /etc/dconf/db/gdm.d/ || exit 1
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
