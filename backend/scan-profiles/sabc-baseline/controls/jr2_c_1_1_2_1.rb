control 'JR2.C.1.1.2.1' do
  title 'Ensure /tmp is a separate partition.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_1_2_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -nk /tmp
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      findmnt -nk /tmp
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
