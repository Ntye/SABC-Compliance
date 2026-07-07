control 'JR2.C.2.2.11' do
  title 'Ensure HTTP Proxy Server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_11'
  if os.debian?
    describe package('squid') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('squid') do
      it { should_not be_installed }
    end
  end
end
