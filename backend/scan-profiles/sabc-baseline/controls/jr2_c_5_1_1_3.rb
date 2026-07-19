control 'JR2.C.5.1.1.3' do
  title 'Ensure journald is configured to write logfiles to persistent disk.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_1_3'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
grep -Ehs '^[[:space:]]*Storage[[:space:]]*=' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*.conf 2>/dev/null | tail -1 | grep -qi 'persistent' && exit 0
exit 1
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
grep -Ersq '^\s*Storage=persistent' /etc/systemd/journald.conf /etc/systemd/journald.conf.d 2>/dev/null
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
