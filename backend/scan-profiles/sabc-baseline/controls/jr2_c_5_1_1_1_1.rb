control 'JR2.C.5.1.1.1.1' do
  title 'Ensure systemd-journal-remote is installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_1_1_1'
  if os[:family] == 'debian'
    describe package('systemd-journal-remote') do
      it { should be_installed }
    end
  end
  if os[:family] == 'redhat'
    describe package('systemd-journal-remote') do
      it { should be_installed }
    end
  end
end
