control 'JR2.C.2.3.3' do
  title 'Ensure talk client is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_3_3'
  if os.debian?
    describe package('talk') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('talk') do
      it { should_not be_installed }
    end
  end
end
