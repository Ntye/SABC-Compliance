control 'JR2.C.3.4.1.1' do
  title 'Ensure ufw is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_1_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' ufw
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      rpm -q firewalld
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
