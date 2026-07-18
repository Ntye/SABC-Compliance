control 'JR2.C.2.2.8' do
  title 'Ensure HTTP server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_8'
  if os.debian?
    describe package('apache2') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
      rpm -q httpd nginx
      systemctl show httpd.socket httpd.service -p UnitFileState,ActiveState |
      systemctl show nginx.service -p UnitFileState,ActiveState | grep -Pi
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
