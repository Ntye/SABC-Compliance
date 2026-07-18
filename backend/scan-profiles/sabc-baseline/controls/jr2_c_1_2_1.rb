control 'JR2.C.1.2.1' do
  title 'Ensure AIDE is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_2_1'
  if os.debian?
    describe package('aide') do
      it { should be_installed }
    end
    describe package('aide-common') do
      it { should be_installed }
    end
  end
  if os.redhat?
    describe package('aide') do
      it { should be_installed }
    end
  end
end
