control 'JR2.C.5.1.2.1' do
  title 'Ensure rsyslog is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_2_1'
  if os.debian?
    describe package('rsyslog') do
      it { should be_installed }
    end
  end
  if os.redhat?
    describe package('rsyslog') do
      it { should be_installed }
    end
  end
end
