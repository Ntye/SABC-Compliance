control 'JR2.C.2.2.7' do
  title 'Ensure FTP Server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_7'
  if os.debian?
    describe package('vsftpd') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('vsftpd') do
      it { should_not be_installed }
    end
  end
end
