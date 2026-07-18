control 'JR2.C.2.2.4' do
  title 'Ensure LDAP server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_4'
  if os.debian?
    describe package('slapd') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('openldap-servers') do
      it { should_not be_installed }
    end
  end
end
