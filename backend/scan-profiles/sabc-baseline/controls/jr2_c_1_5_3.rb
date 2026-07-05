control 'JR2.C.1.5.3' do
  title 'Ensure all AppArmor Profiles are in enforce or complain mode.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_5_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      apparmor_status | grep profiles
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      getenforce
      grep -Pi '^\h*SELINUX=enforcing' /etc/selinux/config
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
