control 'JR2.C.6.2.1' do
  title 'Ensure accounts in /etc/passwd use shadowed passwords.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      awk -F: '($2 != "x" ) { print $1 " is not set to shadowed passwords "}' /etc/passwd
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      awk -F: '($2 != "x" ) { print $1 " is not set to shadowed passwords "}' /etc/passwd
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
