# JR2.C.3.1.1 (CIS Level 1) — Ensure wireless interfaces are disabled.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_1_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_1_1_debian':
      command  => @(SABC_CMD/L),
        #!/usr/bin/env bash
        
        {
         module_fix()
         {
         if ! modprobe -n -v "$l_mname" | grep -P -- '^\h*install \/bin\/(true|false)'; then
         echo -e " - setting module: \"$l_mname\" to be un-loadable"
         echo -e "install $l_mname /bin/false" >> /etc/modprobe.d/"$l_mname".conf
         fi
         if lsmod | grep "$l_mname" > /dev/null 2> then
         echo -e " - unloading module \"$l_mname\""
         modprobe -r "$l_mname"
         fi
         if ! grep -Pq -- "^\h*blacklist\h+$l_mname\b" /etc/modprobe.d/*; then
         echo -e " - deny listing \"$l_mname\""
         echo -e "blacklist $l_mname" >> /etc/modprobe.d/"$l_mname".conf
         fi
         }
         if [ -n "$(find /sys/class/net/*/ -type d -name wireless)" ]; then
         l_dname=$(for driverdir in $(find /sys/class/net/*/ -type d -name wireless | xargs -0 dirname); do basename "$(readlink -f "$driverdir"/device/driver/module)";done | sort -u)
         for l_mname in $l_dname; do
         module_fix
         done
         fi
        }
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         l_output="" l_output2=""
         module_chk()
         {
         # Check how module will be loaded
         l_loadable="$(modprobe -n -v "$l_mname")"
         if grep -Pq -- '^\h*install \/bin\/(true|false)' <<< "$l_loadable"; then
         l_output="$l_output\n - module: \"$l_mname\" is not loadable: \"$l_loadable\""
         else
         l_output2="$l_output2\n - module: \"$l_mname\" is loadable: \"$l_loadable\""
         fi
         # Check is the module currently loaded
         if ! lsmod | grep "$l_mname" > /dev/null 2> then
         l_output="$l_output\n - module: \"$l_mname\" is not loaded"
         else
         l_output2="$l_output2\n - module: \"$l_mname\" is loaded"
         fi
         # Check if the module is deny listed
         if modprobe --showconfig | grep -Pq -- "^\h*blacklist\h+$l_mname\b"; then
         l_output="$l_output\n - module: \"$l_mname\" is deny listed in: \"$(grep -Pl -- "^\h*blacklist\h+$l_mname\b" /etc/modprobe.d/*)\""
         else
         l_output2="$l_output2\n - module: \"$l_mname\" is not deny listed"
         fi
         }
         if [ -n "$(find /sys/class/net/*/ -type d -name wireless)" ]; then
         l_dname=$(for driverdir in $(find /sys/class/net/*/ -type d -name wireless | xargs -0 dirname); do basename "$(readlink -f "$driverdir"/device/driver/module)";done | sort -u)
         for l_mname in $l_dname; do
         module_chk
         done
         fi
         # Report results. If no failures output in l_output2, we pass
         if [ -z "$l_output2" ]; then
         echo -e "\n- Audit Result:\n ** PASS **"
         if [ -z "$l_output" ]; then
         echo -e "\n - System has no wireless NICs installed"
         else
         echo -e "\n$l_output\n"
         fi
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
    exec { 'sabc_jr2_c_3_1_1_redhat':
      command  => @(SABC_CMD/L),
        #!/usr/bin/env bash
        
        {
         module_fix()
         {
         if ! modprobe -n -v "$l_mname" | grep -P -- '^\h*install \/bin\/(true|false)'; then
         echo -e " - setting module: \"$l_mname\" to be un-loadable"
         echo -e "install $l_mname /bin/false" >> /etc/modprobe.d/"$l_mname".conf
         fi
         if lsmod | grep "$l_mname" > /dev/null 2> then
         echo -e " - unloading module \"$l_mname\""
         modprobe -r "$l_mname"
         fi
         if ! grep -Pq -- "^\h*blacklist\h+$l_mname\b" /etc/modprobe.d/*; then
         echo -e " - deny listing \"$l_mname\""
         echo -e "blacklist $l_mname" >> /etc/modprobe.d/"$l_mname".conf
         fi
         }
         if [ -n "$(find /sys/class/net/*/ -type d -name wireless)" ]; then
         l_dname=$(for driverdir in $(find /sys/class/net/*/ -type d -name wireless | xargs -0 dirname); do basename "$(readlink -f "$driverdir"/device/driver/module)";done | sort -u)
         for l_mname in $l_dname; do
         module_fix
         done
         fi
        }
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         l_output="" l_output2=""
         module_chk()
         {
         # Check how module will be loaded
         l_loadable="$(modprobe -n -v "$l_mname")"
         if grep -Pq -- '^\h*install \/bin\/(true|false)' <<< "$l_loadable"; then
         l_output="$l_output\n - module: \"$l_mname\" is not loadable: \"$l_loadable\""
         else
         l_output2="$l_output2\n - module: \"$l_mname\" is loadable: \"$l_loadable\""
         fi
         # Check is the module currently loaded
         if ! lsmod | grep "$l_mname" > /dev/null 2> then
         l_output="$l_output\n - module: \"$l_mname\" is not loaded"
         else
         l_output2="$l_output2\n - module: \"$l_mname\" is loaded"
         fi
         # Check if the module is deny listed
         if modprobe --showconfig | grep -Pq -- "^\h*blacklist\h+$l_mname\b"; then
         l_output="$l_output\n - module: \"$l_mname\" is deny listed in: \"$(grep -Pl -- "^\h*blacklist\h+$l_mname\b" /etc/modprobe.d/*)\""
         else
         l_output2="$l_output2\n - module: \"$l_mname\" is not deny listed"
         fi
         }
         if [ -n "$(find /sys/class/net/*/ -type d -name wireless)" ]; then
         l_dname=$(for driverdir in $(find /sys/class/net/*/ -type d -name wireless | xargs -0 dirname); do basename "$(readlink -f "$driverdir"/device/driver/module)";done | sort -u)
         for l_mname in $l_dname; do
         module_chk
         done
         fi
         # Report results. If no failures output in l_output2, we pass
         if [ -z "$l_output2" ]; then
         echo -e "\n- Audit Result:\n ** PASS **"
         if [ -z "$l_output" ]; then
         echo -e "\n - System has no wireless NICs installed"
         else
         echo -e "\n$l_output\n"
         fi
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
