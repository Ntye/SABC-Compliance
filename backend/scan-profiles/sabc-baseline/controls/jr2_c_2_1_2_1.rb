control 'JR2.C.2.1.2.1' do
  title 'Ensure chrony is running as user _chrony.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_1_2_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      ps -ef | awk '(/[c]hronyd/ && $1!="_chrony") { print $1 }'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      ps -ef | awk '(/[c]hronyd/ && $1!="_chrony") { print $1 }'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
