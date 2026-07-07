control 'JR2.C.1.1.1' do
  title 'Disable Automounting.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_1_1'
  if os[:family] == 'debian'
    describe package('autofs') do
      it { should be_installed }
    end
  end
  if os[:family] == 'redhat'
    describe package('autofs') do
      it { should be_installed }
    end
  end
end
