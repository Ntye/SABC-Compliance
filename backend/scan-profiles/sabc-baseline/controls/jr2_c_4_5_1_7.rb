control 'JR2.C.4.5.1.7' do
  title 'Ensure preventing the use of dictionary words for passwords is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1_7'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Pi '^\h*dictcheck\h*=\h*[^0]' /etc/security/pwquality.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Pi '^\h*dictcheck\h*=\h*[^0]' /etc/security/pwquality.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
