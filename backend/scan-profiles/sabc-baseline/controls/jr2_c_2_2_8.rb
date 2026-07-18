control 'JR2.C.2.2.8' do
  title 'Ensure HTTP server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_8'
  if os.debian?
    describe package('apache2') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('httpd') do
      it { should_not be_installed }
    end
  end
end
