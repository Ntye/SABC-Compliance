control 'JR2.C.3.4.2.2' do
  title 'Ensure ufw is uninstalled or disabled with nftables.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_2_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' ufw
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -P '^\h*FirewallBackend=nftables' /etc/firewalld/firewalld.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
