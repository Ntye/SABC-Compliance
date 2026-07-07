control 'JR2.C.2.2.1' do
  title 'Ensure Avahi Server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_1'
  if os.debian?
    describe package('avahi-daemon') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('avahi-daemon') do
      it { should_not be_installed }
    end
  end
end
