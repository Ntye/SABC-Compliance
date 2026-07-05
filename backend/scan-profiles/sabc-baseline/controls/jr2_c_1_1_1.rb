control 'JR2.C.1.1.1' do
  title 'Disable Automounting.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_1_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' autofs
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      rpm -q autofs
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
