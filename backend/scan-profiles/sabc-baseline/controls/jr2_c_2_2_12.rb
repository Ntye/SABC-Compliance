control 'JR2.C.2.2.12' do
  title 'Ensure SNMP Server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_12'
  if os.debian?
    describe package('snmpd') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    describe package('snmpd') do
      it { should_not be_installed }
    end
  end
end
