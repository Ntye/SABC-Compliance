control 'JR2.C.2.3.1' do
  title 'Ensure NIS Client is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_3_1'
  if os.debian?
    describe package('nis') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('nis') do
      it { should_not be_installed }
    end
  end
end
