#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true

{
    l_option="net.ipv4.conf.all.rp_filter" l_value="1"
    l_grep="${l_option//./(\\.|\\/)}" a_files=()
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
    grep -Pio -- '^\h*#\h*\/[^#\n\r\h]+\.conf\b')
    for l_file in "${a_files[@]}"; do
       grep -Poi -- '\h*'"$l_grep"'\h*=\h*\H+\b' "$l_file" \
       | grep -Pivq -- '^\h*'"$l_grep"'\h*=\h*'"$l_value"'\b' && \
       sed -ri '/^\s*'"$l_grep"'\s*=\s*(0|[2-9]|1[0-9]+)/s/^/# /' "$l_file"
    done
}

    2. Create or edit a file in the /etc/sysctl.d/ directory ending in .confand edit or
       add the following line:

net.ipv4.conf.all.rp_filter = 1
Example:
# [ ! -d "/etc/sysctl.d/" ] && mkdir -p /etc/sysctl.d/
# printf '%s\n' "" "net.ipv4.conf.all.rp_filter = 1" \
>> /etc/sysctl.d/60-ipv4_sysctl.conf
Note: If the UFW file was the first file listed in the audit, the entry will be commented out
as part of the first step, however updating Uncomplicated Firewall (UFW) may update
this change. In this case the updated entry will supersede the entry being created as
part of this step.

    3. Run the following command to load all sysctl configuration filles:

# sysctl --system
