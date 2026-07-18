control 'JR2.C.2.1.4.1' do
  title 'Ensure ntp access control is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_1_4_1'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      dpkg-query -W ntp >/dev/null 2>&1 || dpkg-query -W ntpsec >/dev/null 2>&1 || exit 101
      f=/etc/ntpsec/ntp.conf; [ -e "$f" ] || f=/etc/ntp.conf
      [ -e "$f" ] || exit 1
      for v in 4 6; do
        line=$(grep -Es "^[[:space:]]*restrict[[:space:]]+(-$v[[:space:]]+)?default\b" "$f" | head -1)
        [ -n "$line" ] || exit 1
        for opt in kod nomodify notrap nopeer noquery; do
          printf '%s' "$line" | grep -qw "$opt" || exit 1
        done
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
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
      #!/usr/bin/env bash
      exit 101
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
