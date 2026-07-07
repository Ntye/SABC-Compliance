control 'JR2.C.2.3.5' do
  title 'Ensure LDAP client is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_3_5'
  if os.debian?
    describe package('ldap-utils') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('ldap-utils') do
      it { should_not be_installed }
    end
  end
end
