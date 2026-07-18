control 'JR2.C.1.5.3' do
  title 'Ensure all AppArmor Profiles are in enforce or complain mode.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_5_3'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      apparmor_status | grep profiles
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
      #!/bin/bash
      [ "$(getenforce 2>/dev/null)" = "Enforcing" ] || exit 1
      grep -Eqs '^[[:space:]]*SELINUX=enforcing' /etc/selinux/config || exit 1
      exit 0
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
