control 'JR2.C.4.2.10' do
  title 'Ensure SSH PermitUserEnvironment is disabled.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_2_10'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep permituserenvironment
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
      sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep permituserenvironment
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
