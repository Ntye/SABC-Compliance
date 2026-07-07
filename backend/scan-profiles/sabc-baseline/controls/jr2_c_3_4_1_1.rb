control 'JR2.C.3.4.1.1' do
  title 'Ensure ufw is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_1_1'
  if os.debian?
    describe package('ufw') do
      it { should be_installed }
    end
  end
  if os.redhat?
    describe package('firewalld') do
      it { should be_installed }
    end
  end
end
