control 'JR2.C.4.4.2' do
  title 'Ensure lockout for failed password attempts is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_4_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep 'pam_tally2' /etc/pam.d/common-auth
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -P '^\h*(minlen|minclass|dcredit|ucredit|ocredit|lcredit)' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
