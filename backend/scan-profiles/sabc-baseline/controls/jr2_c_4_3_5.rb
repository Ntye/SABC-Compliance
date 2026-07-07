control 'JR2.C.4.3.5' do
  title 'Ensure sudo authentication timeout is configured correctly.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_3_5'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      vals=$(grep -rhoPs 'timestamp_timeout[[:space:]]*=[[:space:]]*\K-?[0-9]+' /etc/sudoers /etc/sudoers.d 2>/dev/null)
      if [ -z "$vals" ]; then
        d=$(sudo -V 2>/dev/null | grep -oP 'Authentication timestamp timeout:[[:space:]]*\K-?[0-9]+')
        [ -n "$d" ] && [ "$d" -ge 0 ] && [ "$d" -le 15 ] && exit 0
        exit 1
      fi
      for v in $vals; do
        [ "$v" -ge 0 ] && [ "$v" -le 15 ] || exit 1
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
      #!/bin/bash
      vals=$(grep -rhoPs 'timestamp_timeout[[:space:]]*=[[:space:]]*\K-?[0-9]+' /etc/sudoers /etc/sudoers.d 2>/dev/null)
      if [ -z "$vals" ]; then
        d=$(sudo -V 2>/dev/null | grep -oP 'Authentication timestamp timeout:[[:space:]]*\K-?[0-9]+')
        [ -n "$d" ] && [ "$d" -ge 0 ] && [ "$d" -le 15 ] && exit 0
        exit 1
      fi
      for v in $vals; do
        [ "$v" -ge 0 ] && [ "$v" -le 15 ] || exit 1
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
