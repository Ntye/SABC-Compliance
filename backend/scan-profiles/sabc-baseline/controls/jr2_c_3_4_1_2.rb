control 'JR2.C.3.4.1.2' do
  title 'Ensure iptables-persistent is not installed with ufw.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_1_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
dpkg-query -W ufw >/dev/null 2>&1 || exit 101
dpkg-query -W iptables-persistent >/dev/null 2>&1 && exit 1
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
end
