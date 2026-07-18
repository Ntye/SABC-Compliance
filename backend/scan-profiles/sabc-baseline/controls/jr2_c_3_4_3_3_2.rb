control 'JR2.C.3.4.3.3.2' do
  title 'Ensure ip6tables loopback traffic is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_3_3_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
      systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 101
      command -v ip6tables >/dev/null 2>&1 || exit 1
      ip6tables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || exit 1
      ip6tables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || exit 1
      ip6tables -C INPUT -s ::1 -j DROP >/dev/null 2>&1 || exit 1
      exit 0
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
      firewall-cmd --get-zone-of-interface=lo
      firewall-cmd --list-all --zone="$(firewall-cmd --get-zone-of-interface=lo |
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
