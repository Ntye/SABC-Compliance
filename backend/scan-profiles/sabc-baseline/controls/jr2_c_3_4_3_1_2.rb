control 'JR2.C.3.4.3.1.2' do
  title 'Ensure nftables is not installed with iptables.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_3_1_2'
  if os[:family] == 'debian'
    describe package('nftables') do
      it { should_not be_installed }
    end
  end
  if os[:family] == 'redhat'
    describe package('nftables') do
      it { should_not be_installed }
    end
  end
end
