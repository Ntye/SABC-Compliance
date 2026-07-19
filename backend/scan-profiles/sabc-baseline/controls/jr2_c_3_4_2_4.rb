control 'JR2.C.3.4.2.4' do
  title 'Ensure nftables base chains exist.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_2_4'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
dpkg-query -W nftables >/dev/null 2>&1 || exit 101
r=$(nft list ruleset 2>/dev/null) || exit 1
printf '%s' "$r" | grep -q 'hook input' || exit 1
printf '%s' "$r" | grep -q 'hook forward' || exit 1
printf '%s' "$r" | grep -q 'hook output' || exit 1
exit 0
SABC_BASH_EOF
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
exec /bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
# N/A when another firewall (firewalld) is the active choice on this node.
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 101
rpm -q nftables >/dev/null 2>&1 || exit 101
nft list ruleset 2>/dev/null | grep -Eq 'hook input' || exit 1
nft list ruleset 2>/dev/null | grep -Eq 'hook forward' || exit 1
nft list ruleset 2>/dev/null | grep -Eq 'hook output' || exit 1
exit 0
SABC_BASH_EOF
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
