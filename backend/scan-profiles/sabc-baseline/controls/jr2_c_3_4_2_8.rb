control 'JR2.C.3.4.2.8' do
  title 'Ensure nftables rules are permanent.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_2_8'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
      dpkg-query -W nftables >/dev/null 2>&1 || exit 101
      grep -Eqs '^[[:space:]]*include[[:space:]]+"/etc/nftables\.d/sabc\.nft"' /etc/nftables.conf && [ -s /etc/nftables.d/sabc.nft ] && exit 0
      exit 1
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
  if os[:family] == 'redhat'
    v_redhat = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
      rpm -q nftables >/dev/null 2>&1 || exit 101
      grep -Eqs '^[[:space:]]*include[[:space:]]+"/etc/nftables/sabc\.nft"' /etc/sysconfig/nftables.conf && [ -s /etc/nftables/sabc.nft ] && exit 0
      exit 1
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
