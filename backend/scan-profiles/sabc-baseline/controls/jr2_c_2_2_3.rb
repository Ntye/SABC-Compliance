control 'JR2.C.2.2.3' do
  title 'Ensure DHCP Server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_3'
  if os.debian?
    describe package('isc-dhcp-server') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
      rpm -q dhcp-server
      systemctl is-enabled dhcpd.service dhcpd6.service 2>/dev/null | grep
      systemctl is-active dhcpd.service dhcpd6.service 2>/dev/null | grep
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
