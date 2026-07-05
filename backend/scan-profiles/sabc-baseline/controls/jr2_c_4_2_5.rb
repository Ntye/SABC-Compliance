control 'JR2.C.4.2.5' do
  title 'Ensure SSH LogLevel is appropriate.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_2_5'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep loglevel
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep loglevel
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
