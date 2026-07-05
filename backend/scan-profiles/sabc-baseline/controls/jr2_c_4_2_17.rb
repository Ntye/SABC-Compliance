control 'JR2.C.4.2.17' do
  title 'Ensure SSH MaxStartups is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_2_17'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep -i maxstartups
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep -i maxstartups
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
