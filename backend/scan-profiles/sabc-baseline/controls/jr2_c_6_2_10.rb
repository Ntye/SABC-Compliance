control 'JR2.C.6.2.10' do
  title 'Ensure root is the only UID 0 account.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_10'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      awk -F: '($3 == 0) { print $1 }' /etc/passwd
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      awk -F: '($3 == 0) { print $1 }' /etc/passwd
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
