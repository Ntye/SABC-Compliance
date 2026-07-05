control 'JR2.C.6.2.2' do
  title 'Ensure /etc/shadow password fields are not empty.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      awk -F: '($2 == "" ) { print $1 " does not have a password "}' /etc/shadow
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      awk -F: '($2 == "" ) { print $1 " does not have a password "}' /etc/shadow
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
