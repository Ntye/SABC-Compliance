control 'JR2.C.1.4.1' do
  title 'Ensure prelink is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_4_1'
  if os.debian?
    describe package('prelink') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('prelink') do
      it { should_not be_installed }
    end
  end
end
