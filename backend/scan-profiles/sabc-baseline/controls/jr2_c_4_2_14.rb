control 'JR2.C.4.2.14' do
  title 'Ensure only strong Key Exchange algorithms are used.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_2_14'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep kexalgorithms
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
echo "$T" | grep '^kexalgorithms ' | grep -Eq '(diffie-hellman-group1-sha1|diffie-hellman-group14-sha1|diffie-hellman-group-exchange-sha1)' && exit 1
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
