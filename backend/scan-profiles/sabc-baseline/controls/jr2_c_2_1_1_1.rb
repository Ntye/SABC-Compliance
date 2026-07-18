control 'JR2.C.2.1.1.1' do
  title 'Ensure a single time synchronization daemon is in use.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_1_1_1'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
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
    describe package('chrony') do
      it { should be_installed }
    end
  end
end
