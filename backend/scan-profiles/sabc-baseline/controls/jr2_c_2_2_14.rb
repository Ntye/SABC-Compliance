control 'JR2.C.2.2.14' do
  title 'Ensure dnsmasq is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_14'
  if os.debian?
    describe package('dnsmasq') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('dnsmasq') do
      it { should_not be_installed }
    end
  end
end
