control 'JR2.C.4.2.10' do
  title 'Ensure SSH PermitUserEnvironment is disabled.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_2_10'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep permituserenvironment
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep permituserenvironment
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
