control 'JR2.C.4.2.20' do
  title 'Ensure SSH Idle Timeout Interval is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_2_20'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep clientaliveinterval
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
command -v sshd >/dev/null 2>&1 || exit 101
T=$(sshd -T 2>/dev/null) || exit 1
i=$(echo "$T" | awk '$1=="clientaliveinterval"{print $2}')
c=$(echo "$T" | awk '$1=="clientalivecountmax"{print $2}')
[ -n "$i" ] && [ -n "$c" ] && [ "$i" -ge 1 ] && [ "$c" -ge 1 ]
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
