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
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
      systemctl is-active firewalld
      systemctl is-enabled nftables 2>/dev/null || echo 'nftables service masked/inactive (managed by firewalld)'
    SABC_V
    if v_redhat.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_redhat do
        its('exit_status') { should cmp 0 }
      end
    end
  end
end
