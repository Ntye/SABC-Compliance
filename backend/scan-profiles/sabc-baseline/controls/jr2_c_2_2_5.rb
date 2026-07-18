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
    describe package('nfs-utils') do
      it { should_not be_installed }
    end
  end
end
