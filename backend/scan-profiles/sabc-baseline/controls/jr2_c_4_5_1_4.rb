control 'JR2.C.4.5.1.4' do
  title 'Ensure inactive password lock is 30 days or less.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1_4'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      useradd -D | grep INACTIVE
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      useradd -D | grep INACTIVE
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
