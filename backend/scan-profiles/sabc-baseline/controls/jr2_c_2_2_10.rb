control 'JR2.C.2.2.10' do
  title 'Ensure Samba is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_10'
  if os.debian?
    describe package('samba') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('samba') do
      it { should_not be_installed }
    end
  end
end
