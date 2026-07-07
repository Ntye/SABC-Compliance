control 'JR2.C.1.5.1' do
  title 'Ensure AppArmor is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_5_1'
  if os[:family] == 'debian'
    describe package('apparmor') do
      it { should be_installed }
    end
    describe package('apparmor-utils') do
      it { should be_installed }
    end
  end
  if os[:family] == 'redhat'
    describe package('libselinux') do
      it { should be_installed }
    end
    describe package('selinux-policy-targeted') do
      it { should be_installed }
    end
  end
end
