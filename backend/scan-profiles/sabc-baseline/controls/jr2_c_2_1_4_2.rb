control 'JR2.C.2.1.4.2' do
  title 'Ensure ntp is running as user ntp.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_1_4_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      ps -ef | awk '(/[n]tpd/ && $1!="ntp") { print $1 }'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      ps -ef | awk '(/[n]tpd/ && $1!="ntp") { print $1 }'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
