control 'JR2.C.1.7.9' do
  title 'Ensure XDCMP is not enabled.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_7_9'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
dpkg-query -W gdm3 >/dev/null 2>&1 || exit 101
grep -Eqsi '^[[:space:]]*Enable[[:space:]]*=[[:space:]]*true' /etc/gdm3/custom.conf /etc/gdm/custom.conf 2>/dev/null && exit 1
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
rpm -q gdm >/dev/null 2>&1 || exit 101
[ -f /etc/gdm/custom.conf ] || exit 0
awk '/^\[xdmcp\]/{f=1;next} /^\[/{f=0} f && /^\s*Enable\s*=\s*true/{found=1} END{exit found?1:0}' /etc/gdm/custom.conf
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
