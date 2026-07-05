control 'JR2.C.2.2.11' do
  title 'Ensure HTTP Proxy Server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_11'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' squid
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      rpm -q squid
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
