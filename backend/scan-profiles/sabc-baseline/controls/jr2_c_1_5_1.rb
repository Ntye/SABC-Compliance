control 'JR2.C.1.5.1' do
  title 'Ensure AppArmor is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_5_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' apparmor apparmor-utils
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      rpm -q libselinux selinux-policy-targeted
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
