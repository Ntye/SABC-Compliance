control 'JR2.C.4.3.1' do
  title 'Ensure sudo is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_3_1'
  if os[:family] == 'debian'
    describe package('sudo') do
      it { should be_installed }
    end
    describe package('sudo-ldap') do
      it { should be_installed }
    end
    describe package('>') do
      it { should be_installed }
    end
    describe package('/dev/null') do
      it { should be_installed }
    end
    describe package('2>&1') do
      it { should be_installed }
    end
    describe package('&&') do
      it { should be_installed }
    end
    describe package('dpkg-query') do
      it { should be_installed }
    end
    describe package('sudo') do
      it { should be_installed }
    end
    describe package('sudo-ldap') do
      it { should be_installed }
    end
    describe package('|') do
      it { should be_installed }
    end
    describe package('awk') do
      it { should be_installed }
    end
    describe package('&&') do
      it { should be_installed }
    end
    describe package('{print') do
      it { should be_installed }
    end
    describe package('"\n""PASS:""\n""Package') do
      it { should be_installed }
    end
    describe package('is') do
      it { should be_installed }
    end
    describe package('||') do
      it { should be_installed }
    end
    describe package('echo') do
      it { should be_installed }
    end
    describe package('"\nFAIL:\nneither') do
      it { should be_installed }
    end
    describe package('\"sudo\"') do
      it { should be_installed }
    end
    describe package('or') do
      it { should be_installed }
    end
    describe package('\"sudo-ldap\"') do
      it { should be_installed }
    end
    describe package('package') do
      it { should be_installed }
    end
    describe package('is') do
      it { should be_installed }
    end
    describe package('installed\n"') do
      it { should be_installed }
    end
  end
  if os[:family] == 'redhat'
    describe package('sudo') do
      it { should be_installed }
    end
    describe package('sudo-ldap') do
      it { should be_installed }
    end
    describe package('>') do
      it { should be_installed }
    end
    describe package('/dev/null') do
      it { should be_installed }
    end
    describe package('2>&1') do
      it { should be_installed }
    end
    describe package('&&') do
      it { should be_installed }
    end
    describe package('rpm') do
      it { should be_installed }
    end
    describe package('sudo') do
      it { should be_installed }
    end
    describe package('sudo-ldap') do
      it { should be_installed }
    end
    describe package('|') do
      it { should be_installed }
    end
    describe package('awk') do
      it { should be_installed }
    end
    describe package('&&') do
      it { should be_installed }
    end
    describe package('{print') do
      it { should be_installed }
    end
    describe package('"\n""PASS:""\n""Package') do
      it { should be_installed }
    end
    describe package('is') do
      it { should be_installed }
    end
    describe package('||') do
      it { should be_installed }
    end
    describe package('echo') do
      it { should be_installed }
    end
    describe package('"\nFAIL:\nneither') do
      it { should be_installed }
    end
    describe package('\"sudo\"') do
      it { should be_installed }
    end
    describe package('or') do
      it { should be_installed }
    end
    describe package('\"sudo-ldap\"') do
      it { should be_installed }
    end
    describe package('package') do
      it { should be_installed }
    end
    describe package('is') do
      it { should be_installed }
    end
    describe package('installed\n"') do
      it { should be_installed }
    end
  end
end
