control 'JR2.C.2.3.6' do
  title 'Ensure RPC is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_3_6'
  if os.debian?
    describe package('rpcbind') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('rpcbind') do
      it { should_not be_installed }
    end
  end
end
