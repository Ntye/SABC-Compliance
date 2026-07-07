control 'JR2.C.6.1.10' do
  title 'Ensure permissions on /etc/opasswd are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_1_10'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      for f in /etc/security/opasswd /etc/security/opasswd.old; do
        [ -e "$f" ] || continue
        [ "$(stat -c '%a %U %G' "$f")" = "600 root root" ] || exit 1
      done
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
  if os[:family] == 'redhat'
    v_redhat = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      for f in /etc/security/opasswd /etc/security/opasswd.old; do
        [ -e "$f" ] || continue
        [ "$(stat -c '%a %U %G' "$f")" = "600 root root" ] || exit 1
      done
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
