# JR2.C.2.1.1.1 (CIS Level 1) — Ensure a single time synchronization daemon is in use.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_1_1_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_1_1_1_debian':
      command  => @(SABC_CMD/L),
        apt install chrony
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         output="" l_tsd="" l_sdtd="" chrony="" l_ntp=""
         dpkg-query -W chrony > /dev/null 2>&1 && l_chrony="y"
         dpkg-query -W ntp > /dev/null 2>&1 && l_ntp="y" || l_ntp=""
         systemctl list-units --all --type=service | grep -q 'systemd-timesyncd.service' && systemctl is-enabled systemd-timesyncd.service | grep -q 'enabled' && l_sdtd="y"
         if [[ "$l_chrony" = "y" && "$l_ntp" != "y" && "$l_sdtd" != "y" ]]; then
         l_tsd="chrony"
         output="$output\n- chrony is in use on the system"
         elif [[ "$l_chrony" != "y" && "$l_ntp" = "y" && "$l_sdtd" != "y" ]]; then
         l_tsd="ntp"
         output="$output\n- ntp is in use on the system"
         elif [[ "$l_chrony" != "y" && "$l_ntp" != "y" ]]; then
         if systemctl list-units --all --type=service | grep -q 'systemd-timesyncd.service' && systemctl is-enabled systemd-timesyncd.service | grep -Eq '(enabled|disabled|masked)'; then
         l_tsd="sdtd"
         output="$output\n- systemd-timesyncd is in use on the system"
         fi
         else
         [[ "$l_chrony" = "y" && "$l_ntp" = "y" ]] && output="$output\n- both chrony and ntp are in use on the system"
         [[ "$l_chrony" = "y" && "$l_sdtd" = "y" ]] && output="$output\n- both chrony and systemd-timesyncd are in use on the system"
         [[ "$l_ntp" = "y" && "$l_sdtd" = "y" ]] && output="$output\n- both ntp and systemd-timesyncd are in use on the system"
         fi
         if [ -n "$l_tsd" ]; then
         echo -e "\n- PASS:\n$output\n"
         else
         echo -e "\n- FAIL:\n$output\n"
         fi
        }
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_1_1_1_redhat':
      command  => @(SABC_CMD/L),
        dnf install -y chrony
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         output="" l_tsd="" l_sdtd="" chrony="" l_ntp=""
         rpm -q chrony > /dev/null 2>&1 && l_chrony="y"
         rpm -q ntp > /dev/null 2>&1 && l_ntp="y" || l_ntp=""
         systemctl list-units --all --type=service | grep -q 'systemd-timesyncd.service' && systemctl is-enabled systemd-timesyncd.service | grep -q 'enabled' && l_sdtd="y"
         if [[ "$l_chrony" = "y" && "$l_ntp" != "y" && "$l_sdtd" != "y" ]]; then
         l_tsd="chrony"
         output="$output\n- chrony is in use on the system"
         elif [[ "$l_chrony" != "y" && "$l_ntp" = "y" && "$l_sdtd" != "y" ]]; then
         l_tsd="ntp"
         output="$output\n- ntp is in use on the system"
         elif [[ "$l_chrony" != "y" && "$l_ntp" != "y" ]]; then
         if systemctl list-units --all --type=service | grep -q 'systemd-timesyncd.service' && systemctl is-enabled systemd-timesyncd.service | grep -Eq '(enabled|disabled|masked)'; then
         l_tsd="sdtd"
         output="$output\n- systemd-timesyncd is in use on the system"
         fi
         else
         [[ "$l_chrony" = "y" && "$l_ntp" = "y" ]] && output="$output\n- both chrony and ntp are in use on the system"
         [[ "$l_chrony" = "y" && "$l_sdtd" = "y" ]] && output="$output\n- both chrony and systemd-timesyncd are in use on the system"
         [[ "$l_ntp" = "y" && "$l_sdtd" = "y" ]] && output="$output\n- both ntp and systemd-timesyncd are in use on the system"
         fi
         if [ -n "$l_tsd" ]; then
         echo -e "\n- PASS:\n$output\n"
         else
         echo -e "\n- FAIL:\n$output\n"
         fi
        }
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
