control 'JR2.C.2.3.4' do
  title 'Ensure telnet client is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_3_4'
  if os.debian?
    describe package('telnet') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('telnet') do
      it { should_not be_installed }
    end
  end
end
