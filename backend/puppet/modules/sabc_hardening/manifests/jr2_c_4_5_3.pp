# JR2.C.4.5.3 (CIS Level 1) — Ensure default user shell timeout is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_5_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_5_3_debian':
      command  => @(SABC_CMD/L),
        TMOUT=900
        readonly TMOUT
        export TMOUT
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         l_output="" l_output2=""
         l_tmv_max="900"
         l_searchloc="/etc/bashrc /etc/bash.bashrc /etc/profile /etc/profile.d/*.sh"
         a_tmofile=()
         while read -r l_file; do
         [ -e "$l_file" ] && a_tmofile+=("$(readlink -f $l_file)")
         done < <(grep -PRils '^\h*([^#\n\r]+\h+)?TMOUT=\d+\b' $l_searchloc)
         if ! (( ${#a_tmofile[@]} > 0 )); then
         l_output2="$l_output2\n - TMOUT is not set"
         elif (( ${#a_tmofile[@]} > 1 )); then
         l_output2="$l_output2\n - TMOUT is set in multiple locations.\n - List of files where TMOUT is set:\n$(printf '%s\n' "${a_tmofile[@]}")\n - end of list\n"
         else
         for l_file in ${a_tmofile[@]}; do
         if (( "$(grep -Pci '^\h*([^#\n\r]+\h+)?TMOUT=\d+' "$l_file")" > 1 )); then
         l_output2="$l_output2\n - TMOUT is set multiple times in \"$l_file\""
         else
         l_tmv="$(grep -Pi '^\h*([^#\n\r]+\h+)?TMOUT=\d+' "$l_file" | grep -Po '\d+')"
         if (( "$l_tmv" > "$l_tmv_max" )); then
         l_output2="$l_output\n - TMOUT is \"$l_tmv\" in \"$l_file\"\n - Should be \"$l_tmv_max\" or less and not \"0\""
         else
         l_output="$l_output\n- TMOUT is correctly set to \"$l_tmv\" in \"$l_file\""
         if grep -Piq '^\h*([^#\n\r]+\h+)?readonly\h+TMOUT\b' "$l_file"; then
         l_output="$l_output\n- TMOUT is correctly set to \"readonly\" in \"$l_file\""
         else
         l_output2="$l_output2\n- TMOUT is not set to \"readonly\""
         fi
         if grep -Piq '^(\h*|\h*[^#\n\r]+\h*;\h*)export\h+TMOUT\b' "$l_file"; then
         l_output="$l_output\n- TMOUT is correctly set to \"export\" in \"$l_file\""
         else
         l_output2="$l_output2\n- TMOUT is not set to \"export\""
         fi
         fi
         fi
         done
         fi
         unset a_tmofile # Remove array
         if [ -z "$l_output2" ]; then
         echo -e "\n- Audit Result:\n ** PASS **\n - * Correctly configured * :\n$l_output\n"
         else
         echo -e "\n- Audit Result:\n ** FAIL **\n - * Reasons for audit failure * :\n$l_output2"
         [ -n "$l_output" ] && echo -e "- * Correctly configured * :\n$l_output\n"
         fi
        }
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_5_3_redhat':
      command  => @(SABC_CMD/L),
        TMOUT=900
        readonly TMOUT
        export TMOUT
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        #!/usr/bin/env bash
        
        {
         l_output="" l_output2=""
         l_tmv_max="900"
         l_searchloc="/etc/bashrc /etc/bash.bashrc /etc/profile /etc/profile.d/*.sh"
         a_tmofile=()
         while read -r l_file; do
         [ -e "$l_file" ] && a_tmofile+=("$(readlink -f $l_file)")
         done < <(grep -PRils '^\h*([^#\n\r]+\h+)?TMOUT=\d+\b' $l_searchloc)
         if ! (( ${#a_tmofile[@]} > 0 )); then
         l_output2="$l_output2\n - TMOUT is not set"
         elif (( ${#a_tmofile[@]} > 1 )); then
         l_output2="$l_output2\n - TMOUT is set in multiple locations.\n - List of files where TMOUT is set:\n$(printf '%s\n' "${a_tmofile[@]}")\n - end of list\n"
         else
         for l_file in ${a_tmofile[@]}; do
         if (( "$(grep -Pci '^\h*([^#\n\r]+\h+)?TMOUT=\d+' "$l_file")" > 1 )); then
         l_output2="$l_output2\n - TMOUT is set multiple times in \"$l_file\""
         else
         l_tmv="$(grep -Pi '^\h*([^#\n\r]+\h+)?TMOUT=\d+' "$l_file" | grep -Po '\d+')"
         if (( "$l_tmv" > "$l_tmv_max" )); then
         l_output2="$l_output\n - TMOUT is \"$l_tmv\" in \"$l_file\"\n - Should be \"$l_tmv_max\" or less and not \"0\""
         else
         l_output="$l_output\n- TMOUT is correctly set to \"$l_tmv\" in \"$l_file\""
         if grep -Piq '^\h*([^#\n\r]+\h+)?readonly\h+TMOUT\b' "$l_file"; then
         l_output="$l_output\n- TMOUT is correctly set to \"readonly\" in \"$l_file\""
         else
         l_output2="$l_output2\n- TMOUT is not set to \"readonly\""
         fi
         if grep -Piq '^(\h*|\h*[^#\n\r]+\h*;\h*)export\h+TMOUT\b' "$l_file"; then
         l_output="$l_output\n- TMOUT is correctly set to \"export\" in \"$l_file\""
         else
         l_output2="$l_output2\n- TMOUT is not set to \"export\""
         fi
         fi
         fi
         done
         fi
         unset a_tmofile # Remove array
         if [ -z "$l_output2" ]; then
         echo -e "\n- Audit Result:\n ** PASS **\n - * Correctly configured * :\n$l_output\n"
         else
         echo -e "\n- Audit Result:\n ** FAIL **\n - * Reasons for audit failure * :\n$l_output2"
         [ -n "$l_output" ] && echo -e "- * Correctly configured * :\n$l_output\n"
         fi
        }
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
