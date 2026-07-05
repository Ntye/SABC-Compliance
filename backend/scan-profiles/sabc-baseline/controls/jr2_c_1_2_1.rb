control 'JR2.C.1.2.1' do
  title 'Ensure AIDE is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_2_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' aide aide-common
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      rpm -q aide aide-common
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
