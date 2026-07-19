control 'JR2.C.3.1.2' do
  title 'Ensure bluetooth is disabled.'
  impact 0.7
  tag cis_level: 2
  tag control_key: 'jr2_c_3_1_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
dpkg-query -W bluez >/dev/null 2>&1 || exit 0
systemctl is-active bluetooth 2>/dev/null | grep -qx active && exit 1
systemctl is-enabled bluetooth 2>/dev/null | grep -q '^enabled' && exit 1
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
installed=0
for p in bluez; do rpm -q "$p" >/dev/null 2>&1 && installed=1; done
[ "$installed" -eq 0 ] && exit 0
# Package present (may be a dependency): its units must be neither enabled nor active.
systemctl is-enabled bluetooth.service 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active bluetooth.service 2>/dev/null | grep -q '^active' && exit 1
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
