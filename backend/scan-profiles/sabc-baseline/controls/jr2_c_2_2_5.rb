control 'JR2.C.2.2.5' do
  title 'Ensure NFS is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_5'
  if os.debian?
    describe package('nfs-kernel-server') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
      rpm -q nfs-utils
      systemctl is-enabled nfs-server.service 2>/dev/null | grep 'enabled'
      systemctl is-active nfs-server.service 2>/dev/null | grep '^active'
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
