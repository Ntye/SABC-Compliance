control 'JR2.C.2.3.2' do
  title 'Ensure rsh client is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_3_2'
  if os.debian?
    describe package('rsh-client') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('rsh-client') do
      it { should_not be_installed }
    end
  end
end
