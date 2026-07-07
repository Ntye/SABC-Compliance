control 'JR2.C.2.2.3' do
  title 'Ensure DHCP Server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_3'
  if os[:family] == 'debian'
    describe package('isc-dhcp-server') do
      it { should_not be_installed }
    end
  end
  if os[:family] == 'redhat'
    describe package('isc-dhcp-server') do
      it { should_not be_installed }
    end
  end
end
