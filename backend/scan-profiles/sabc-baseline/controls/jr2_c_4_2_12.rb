control 'JR2.C.4.2.12' do
  title 'Ensure only strong Ciphers are used.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_2_12'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep ciphers
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep ciphers
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
