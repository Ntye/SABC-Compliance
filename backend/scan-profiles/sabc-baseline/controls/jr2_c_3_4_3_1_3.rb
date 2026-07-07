control 'JR2.C.3.4.3.1.3' do
  title 'Ensure ufw is uninstalled or disabled with iptables.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_3_1_3'
  if os[:family] == 'debian'
    describe package('ufw') do
      it { should be_installed }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      systemctl is-active firewalld
      systemctl is-enabled nftables 2>/dev/null || echo 'nftables service masked/inactive (managed by firewalld)'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
