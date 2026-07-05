control 'JR2.C.3.4.3.3.2' do
  title 'Ensure ip6tables loopback traffic is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_3_3_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      ip6tables -L INPUT -v -n
      ip6tables -L OUTPUT -v -n
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      ip6tables -L INPUT -v -n
      ip6tables -L OUTPUT -v -n
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
