control 'JR2.C.4.4.1' do
  title 'Ensure password creation requirements are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_4_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep '^\s*minlen\s*' /etc/security/pwquality.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -P 'pam_pwquality\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth
      rpm -q libpwquality
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
