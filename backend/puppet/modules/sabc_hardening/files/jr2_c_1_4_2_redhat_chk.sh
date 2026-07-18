#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true

{
      l_parameter_name="kernel.randomize_va_space"
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
      if [ -n "$l_option_value" ]; then
         [ "$l_file" = "$(readlink -e "$l_ufw_file")" ] && \
         a_output+=(" ** \"$l_file\" is UFW's IPT_SYSCTL file **")
         a_output+=(" - \"$l_parameter_name\" is set to: \"$l_option_value\"
in: \"$l_file\"")
      fi
   done
   [ "${#a_output[@]}" -gt "0" ] && printf '%s\n' "" "${a_output[@]}" ""
}
Example output:
 - "kernel.randomize_va_space" is set to: "2" in: "/etc/sysctl.d/60-
kernel_sysctl.conf"
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
