control 'JR2.C.4.3.1' do
  title 'Ensure sudo is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_3_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -W sudo sudo-ldap > /dev/null 2>&1 && dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' sudo sudo-ldap | awk '($4=="installed" && $NF=="installed") {print "\n""PASS:""\n""Package ""\""$1"\""" is installed""\n"}' || echo -e "\nFAIL:\nneither \"sudo\" or \"sudo-ldap\" package is installed\n"
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      rpm -q sudo sudo-ldap > /dev/null 2>&1 && rpm -q sudo sudo-ldap | awk '($4=="installed" && $NF=="installed") {print "\n""PASS:""\n""Package ""\""$1"\""" is installed""\n"}' || echo -e "\nFAIL:\nneither \"sudo\" or \"sudo-ldap\" package is installed\n"
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
