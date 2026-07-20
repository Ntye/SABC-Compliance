control 'JR2.C.3.4.3.1.3' do
  title 'Ensure ufw is uninstalled or disabled with iptables.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_3_1_3'
  if os.debian?
    describe package('ufw') do
      it { should be_installed }
    end
  end
end
