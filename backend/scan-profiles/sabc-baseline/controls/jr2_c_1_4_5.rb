control 'JR2.C.1.4.5' do
  title 'Ensure core dumps are restricted.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_4_5'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      grep -Ersq '^[[:space:]]*\*[[:space:]]+hard[[:space:]]+core[[:space:]]+0\b' /etc/security/limits.conf /etc/security/limits.d 2>/dev/null || exit 1
      [ "$(sysctl -n fs.suid_dumpable 2>/dev/null)" = "0" ] || exit 1
      grep -Ersq '^[[:space:]]*fs\.suid_dumpable[[:space:]]*=[[:space:]]*0\b' /etc/sysctl.conf /etc/sysctl.d 2>/dev/null || exit 1
      if [ -e /etc/systemd/coredump.conf ] || [ -d /etc/systemd/coredump.conf.d ]; then
        grep -Ehs '^[[:space:]]*Storage[[:space:]]*=' /etc/systemd/coredump.conf /etc/systemd/coredump.conf.d/*.conf 2>/dev/null | tail -1 | grep -q 'none' || exit 1
      fi
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
      grep -Ersq '^[[:space:]]*\*[[:space:]]+hard[[:space:]]+core[[:space:]]+0\b' /etc/security/limits.conf /etc/security/limits.d 2>/dev/null || exit 1
      [ "$(sysctl -n fs.suid_dumpable 2>/dev/null)" = "0" ] || exit 1
      grep -Ersq '^[[:space:]]*fs\.suid_dumpable[[:space:]]*=[[:space:]]*0\b' /etc/sysctl.conf /etc/sysctl.d 2>/dev/null || exit 1
      if [ -e /etc/systemd/coredump.conf ] || [ -d /etc/systemd/coredump.conf.d ]; then
        grep -Ehs '^[[:space:]]*Storage[[:space:]]*=' /etc/systemd/coredump.conf /etc/systemd/coredump.conf.d/*.conf 2>/dev/null | tail -1 | grep -q 'none' || exit 1
      fi
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
