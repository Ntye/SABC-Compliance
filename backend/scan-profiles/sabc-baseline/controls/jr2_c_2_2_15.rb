control 'JR2.C.2.2.15' do
  title 'Ensure mail transfer agent is configured for local-only mode.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_15'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      ss -lntu | grep -P ':25\b' | grep -Pv '\h+(127\.0\.0\.1|\[?::1\]?):25\b'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      ss -lntu | grep -P ':25\b' | grep -Pv '\h+(127\.0\.0\.1|\[?::1\]?):25\b'
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
