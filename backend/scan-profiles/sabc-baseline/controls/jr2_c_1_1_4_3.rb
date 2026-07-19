control 'JR2.C.1.1.4.3' do
  title 'Ensure nosuid option set on /var/tmp partition.'
  impact 0.7
  tag cis_level: 2
  tag control_key: 'jr2_c_1_1_4_3'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
findmnt -kn /var/tmp | grep -v 'nosuid'
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
/bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
# N/A when /var/tmp is not a separate mount point on this node.
findmnt -kn /var/tmp >/dev/null 2>&1 || exit 101
findmnt -kn /var/tmp | grep -qw nosuid
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
