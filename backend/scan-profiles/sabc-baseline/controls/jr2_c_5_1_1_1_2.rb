control 'JR2.C.5.1.1.1.2' do
  title 'Ensure journald is not configured to receive logs from a remote client.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_1_1_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
systemctl list-unit-files 2>/dev/null | grep -q '^systemd-journal-remote\.socket' || exit 0
[ "$(systemctl is-enabled systemd-journal-remote.socket 2>/dev/null)" = "masked" ] || exit 1
systemctl is-active systemd-journal-remote.socket 2>/dev/null | grep -qx active && exit 1
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
systemctl is-enabled systemd-journal-remote.socket systemd-journal-remote.service 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active systemd-journal-remote.socket systemd-journal-remote.service 2>/dev/null | grep -q '^active' && exit 1
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
