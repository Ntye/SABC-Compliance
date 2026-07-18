control 'JR2.C.3.3.2' do
  title 'Ensure ICMP redirects are not accepted.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_3_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/usr/bin/env bash
      
      {
       l_output="" l_output2=""
       a_parlist=("net.ipv4.conf.all.accept_redirects=0" "net.ipv4.conf.default.accept_redirects=0" "net.ipv6.conf.all.accept_redirects=0" "net.ipv6.conf.default.accept_redirects=0")
       l_ufwscf="$([ -f /etc/default/ufw ] && awk -F= '/^\s*IPT_SYSCTL=/ {print $2}' /etc/default/ufw)"
       kernel_parameter_chk()
       { 
       l_krp="$(sysctl "$l_kpname" | awk -F= '{print $2}' | xargs)" # Check running configuration
       if [ "$l_krp" = "$l_kpvalue" ]; then
       l_output="$l_output\n - \"$l_kpname\" is correctly set to \"$l_krp\" in the running configuration"
       else
       l_output2="$l_output2\n - \"$l_kpname\" is incorrectly set to \"$l_krp\" in the running configuration and should have a value of: \"$l_kpvalue\""
       fi
       unset A_out; declare -A A_out # Check durable setting (files)
       while read -r l_out; do
       if [ -n "$l_out" ]; then
       if [[ $l_out =~ ^\s*# ]]; then
       l_file="${l_out//# /}"
       else
       l_kpar="$(awk -F= '{print $1}' <<< "$l_out" | xargs)"
       [ "$l_kpar" = "$l_kpname" ] && A_out+=(["$l_kpar"]="$l_file")
       fi
       fi
       done < <(/usr/lib/systemd/systemd-sysctl --cat-config | grep -Po '^\h*([^#\n\r]+|#\h*\/[^#\n\r\h]+\.conf\b)')
       if [ -n "$l_ufwscf" ]; then # Account for systems with UFW (Not covered by systemd-sysctl --cat-config)
       l_kpar="$(grep -Po "^\h*$l_kpname\b" "$l_ufwscf" | xargs)"
       l_kpar="${l_kpar//\//.}"
       [ "$l_kpar" = "$l_kpname" ] && A_out+=(["$l_kpar"]="$l_ufwscf")
       fi
       if (( ${#A_out[@]} > 0 )); then # Assess output from files and generate output
       while IFS="=" read -r l_fkpname l_fkpvalue; do
       l_fkpname="${l_fkpname// /}"; l_fkpvalue="${l_fkpvalue// /}"
       if [ "$l_fkpvalue" = "$l_kpvalue" ]; then
       l_output="$l_output\n - \"$l_kpname\" is correctly set to \"$l_fkpvalue\" in \"$(printf '%s' "${A_out[@]}")\"\n"
       else
       l_output2="$l_output2\n - \"$l_kpname\" is incorrectly set to \"$l_fkpvalue\" in \"$(printf '%s' "${A_out[@]}")\" and should have a value of: \"$l_kpvalue\"\n"
       fi
       done < <(grep -Po -- "^\h*$l_kpname\h*=\h*\H+" "${A_out[@]}")
       else
       l_output2="$l_output2\n - \"$l_kpname\" is not set in an included file\n ** Note: \"$l_kpname\" May be set in a file that's ignored by load procedure **\n"
       fi
       }
       while IFS="=" read -r l_kpname l_kpvalue; do # Assess and check parameters
       l_kpname="${l_kpname// /}"; l_kpvalue="${l_kpvalue// /}"
       if ! grep -Pqs '^\h*0\b' /sys/module/ipv6/parameters/disable && grep -q '^net.ipv6.' <<< "$l_kpname"; then
       l_output="$l_output\n - IPv6 is disabled on the system, \"$l_kpname\" is not applicable"
       else
       kernel_parameter_chk
       fi
       done < <(printf '%s\n' "${a_parlist[@]}")
       if [ -z "$l_output2" ]; then # Provide output from checks
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
      #!/usr/bin/env bash
      
      {
            l_parameter_name="net.ipv4.conf.all.accept_redirects"
            l_grep="${l_parameter_name//./(\\.|\\/)}" a_output=() a_files=()
            l_systemdsysctl="$(readlink -e /lib/systemd/systemd-sysctl \
            || readlink -e /usr/lib/systemd/systemd-sysctl)"
            l_ufw_file="$([ -f /etc/default/ufw ] && \
            awk -F= '/^\s*IPT_SYSCTL=/ {print $2}' /etc/default/ufw)"
            [ -f "$(readlink -e "$l_ufw_file")" ] && \
            a_files+=("$l_ufw_file"); a_files+=("/etc/sysctl.conf")
            while IFS= read -r l_fname; do
               l_file="$(readlink -e "${l_fname//# /}")"
               [ -n "$l_file" ] && ! grep -Psiq -- '(^|\h+)'"$l_file"'\b' \
               <<< "${a_files[*]}" && a_files+=("$l_file")
            done < <("$l_systemdsysctl" --cat-config | tac | \
            grep -Pio '^\h*#\h*\/[^#\n\r\h]+\.conf\b')
            for l_file in "${a_files[@]}"; do
               l_opt="$(grep -Poi '^\h*'"$l_grep"'\h*=\h*\H+\b' "$l_file" | tail -n
      1)"
               l_option_value="$(cut -d= -f2 <<< "$l_opt" | xargs)"
               [ -n "$l_option_value" ] && \
               a_output+=(" - \"$l_parameter_name = $l_option_value\" is set in:" \
               "    \"$l_file\"")
            done
            [ "${#a_output[@]}" -gt "0" ] && printf '%s\n' "" "${a_output[@]}" ""
      }
      Example output:
       - "net.ipv4.conf.all.accept_redirects = 0" is set in: "/etc/sysctl.d/60-
      ipv4_sysctl.conf"
      Note:
      
        •     This script looks at all files used by systemd sysctl.
        •     More information about these files and their location is available in the section
              overview.
        •     If multiple lines are returned:
                  o The first line includes the value being used by systemd sysctl. If this is a
                      correct value, this is considered a passing state. If the file listed is not in
                      the /etc/sysctl.d/ directory, it is highly recommended to follow the
                      remediation procedure to create a .conf file in the /etc/sysctl.d/
                      directory with the correct setting to prevent a potential change due to an
                      update to the system.
                  o Any files in the /etc/sysctl.d/ directory that include an incorrect value
                      should be modified to comment out or change the incorrect value to
                      minimize the potential of the incorrect value being used by systemd
                      sysctl due to system configuration changes.
        •     SYSTEM FILE PRECEDENCE
                  o When using the --system option, sysctl will read files from directories in
                      the following list in given order from top to bottom. Once a file of a given
                      filename is loaded, any file of the same name in subsequent directories is
                      ignored.
                  o /etc/sysctl.d/*.conf /run/sysctl.d/*.conf
                      /usr/local/lib/sysctl.d/*.conf /usr/lib/sysctl.d/*.conf
                      /lib/sysctl.d/*.conf /etc/sysctl.conf
                  o All configuration files are sorted in lexicographic order, regardless of the
                      directory they reside in. Configuration files can either be completely
                      replaced (by having a new configuration file with the same name in a
                      directory of higher priority) or partially replaced (by having a configuration
                      file that is ordered later)--
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
